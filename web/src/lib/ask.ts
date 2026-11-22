/** Client for POST /api/ask: sends the question and turns the SSE response into handler calls. */
import type { PipelineName, PipelineResult, TraceEvent } from './api-types'
import {
  API_ASK_PATH,
  DEFAULT_RETRY_AFTER_S,
  MSG_CONNECTION_CLOSED,
  MSG_NETWORK,
  MSG_REJECTED,
  MSG_SERVER,
  MSG_UNAVAILABLE,
  MSG_UNREADABLE,
} from './config'
import { SseParser } from './sse'
import type { SseFrame } from './sse'

/** What went wrong. "stream" covers an error frame and a dropped or unreadable stream. */
export type AskErrorKind = 'input' | 'rate' | 'unavailable' | 'server' | 'network' | 'stream'

export interface AskError {
  kind: AskErrorKind
  message: string
  /** Seconds to wait; only for kind "rate". */
  retryAfterS?: number
}

export interface AskHandlers {
  onTrace: (event: TraceEvent) => void
  onAnswer: (result: PipelineResult) => void
  onError: (error: AskError) => void
}

/** Anything with Headers.get, so tests can pass a plain object. */
export interface HeaderReader {
  get(name: string): string | null
}

/** The fetch signature askStream needs. */
export type FetchFn = (input: string, init: RequestInit) => Promise<Response>

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** The body's "error" string, or the fallback. */
function bodyError(body: unknown, fallback: string): string {
  if (isRecord(body) && typeof body.error === 'string' && body.error !== '') return body.error
  return fallback
}

/** Seconds from the body's retry_after_s, else the Retry-After header, else the default. */
function retryAfterSeconds(body: unknown, headers: HeaderReader): number {
  if (isRecord(body)) {
    const fromBody = body.retry_after_s
    if (typeof fromBody === 'number' && Number.isFinite(fromBody) && fromBody > 0) return fromBody
  }
  const fromHeader = Number(headers.get('Retry-After'))
  if (Number.isFinite(fromHeader) && fromHeader > 0) return fromHeader
  return DEFAULT_RETRY_AFTER_S
}

/**
 * Map a non-200 response to an AskError. body is the parsed JSON body, or undefined when the
 * body was not JSON.
 */
export function mapErrorResponse(
  status: number,
  body: unknown,
  headers: HeaderReader,
): AskError {
  if (status === 422 || status === 413) {
    return { kind: 'input', message: bodyError(body, MSG_REJECTED) }
  }
  if (status === 429) {
    return {
      kind: 'rate',
      message: bodyError(body, MSG_REJECTED),
      retryAfterS: retryAfterSeconds(body, headers),
    }
  }
  if (status === 503) {
    return { kind: 'unavailable', message: bodyError(body, MSG_UNAVAILABLE) }
  }
  return { kind: 'server', message: MSG_SERVER }
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

type Parsed = { ok: true; value: unknown } | { ok: false }

function parseJson(text: string): Parsed {
  try {
    return { ok: true, value: JSON.parse(text) as unknown }
  } catch (error) {
    if (error instanceof SyntaxError) return { ok: false }
    throw error
  }
}

/**
 * Hand one frame to the handlers. Returns true when the stream is finished (an answer, an
 * error, or unreadable data) and the caller must stop reading.
 */
function dispatchFrame(frame: SseFrame, handlers: AskHandlers): boolean {
  if (frame.type === 'comment') return false
  if (frame.event !== 'trace' && frame.event !== 'answer' && frame.event !== 'error') return false
  const parsed = parseJson(frame.data)
  if (!parsed.ok || !isRecord(parsed.value)) {
    handlers.onError({ kind: 'stream', message: MSG_UNREADABLE })
    return true
  }
  if (frame.event === 'trace') {
    handlers.onTrace(parsed.value as unknown as TraceEvent)
    return false
  }
  if (frame.event === 'answer') {
    handlers.onAnswer(parsed.value as unknown as PipelineResult)
    return true
  }
  handlers.onError({ kind: 'stream', message: bodyError(parsed.value, MSG_SERVER) })
  return true
}

/** Dispatch frames in order; true when one of them ended the stream. */
function dispatchAll(frames: SseFrame[], handlers: AskHandlers, signal: AbortSignal): boolean {
  for (const frame of frames) {
    if (signal.aborted) return true
    if (dispatchFrame(frame, handlers)) return true
  }
  return false
}

/** Read the response body to its end, calling the handlers as frames complete. */
async function readStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  handlers: AskHandlers,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  const parser = new SseParser()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      if (dispatchAll(parser.push(decoder.decode(value, { stream: true })), handlers, signal)) return
    }
    const tail = [...parser.push(decoder.decode()), ...parser.end()]
    if (dispatchAll(tail, handlers, signal)) return
    if (!signal.aborted) handlers.onError({ kind: 'stream', message: MSG_CONNECTION_CLOSED })
  } finally {
    reader.cancel().catch(() => undefined)
  }
}

/** Map a non-200 response, reading its body as JSON when it is JSON. */
async function failFromResponse(response: Response, handlers: AskHandlers): Promise<void> {
  const text = await response.text()
  const parsed = parseJson(text)
  handlers.onError(mapErrorResponse(response.status, parsed.ok ? parsed.value : undefined, response.headers))
}

/**
 * Ask a question and report the stream through the handlers. Resolves when the stream ends.
 * On abort it ends quietly and calls no handler. It never rejects.
 */
export async function askStream(
  question: string,
  pipeline: PipelineName,
  signal: AbortSignal,
  handlers: AskHandlers,
  fetchFn: FetchFn = (input, init) => globalThis.fetch(input, init),
): Promise<void> {
  let response: Response
  try {
    response = await fetchFn(API_ASK_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, pipeline }),
      signal,
    })
  } catch (error) {
    if (signal.aborted || isAbortError(error)) return
    handlers.onError({ kind: 'network', message: MSG_NETWORK })
    return
  }
  try {
    if (response.status !== 200) {
      await failFromResponse(response, handlers)
    } else if (response.body === null) {
      handlers.onError({ kind: 'stream', message: MSG_CONNECTION_CLOSED })
    } else {
      await readStream(response.body, signal, handlers)
    }
  } catch (error) {
    if (signal.aborted || isAbortError(error)) return
    handlers.onError({ kind: 'stream', message: MSG_CONNECTION_CLOSED })
  }
}
