import { describe, expect, it } from 'vitest'
import type { PipelineResult, TraceEvent } from './api-types'
import { askStream, mapErrorResponse } from './ask'
import type { AskError, AskHandlers, FetchFn } from './ask'

const noHeaders = { get: () => null }
const headers = (value: string | null) => ({
  get: (name: string) => (name === 'Retry-After' ? value : null),
})

describe('mapErrorResponse', () => {
  it('maps 422 and 413 to input with the body error', () => {
    expect(mapErrorResponse(422, { error: 'Too short.' }, noHeaders)).toEqual({
      kind: 'input',
      message: 'Too short.',
    })
    expect(mapErrorResponse(413, { error: 'Body too large.' }, noHeaders)).toEqual({
      kind: 'input',
      message: 'Body too large.',
    })
  })

  it('maps 429 with retry_after_s from the body first', () => {
    expect(
      mapErrorResponse(429, { error: 'Slow down.', retry_after_s: 5 }, headers('30')),
    ).toEqual({ kind: 'rate', message: 'Slow down.', retryAfterS: 5 })
  })

  it('falls back to the Retry-After header, then to 60', () => {
    expect(mapErrorResponse(429, { error: 'x' }, headers('12')).retryAfterS).toBe(12)
    expect(mapErrorResponse(429, { error: 'x' }, headers(null)).retryAfterS).toBe(60)
    expect(mapErrorResponse(429, { error: 'x' }, headers('soon')).retryAfterS).toBe(60)
    expect(mapErrorResponse(429, undefined, headers(null)).retryAfterS).toBe(60)
  })

  it('maps 503 to unavailable', () => {
    expect(mapErrorResponse(503, { error: 'Budget used up.' }, noHeaders)).toEqual({
      kind: 'unavailable',
      message: 'Budget used up.',
    })
  })

  it('maps everything else, and a non-JSON body, to server', () => {
    const server = { kind: 'server', message: 'Something went wrong on the server.' }
    expect(mapErrorResponse(500, { error: 'Internal error.' }, noHeaders)).toEqual(server)
    expect(mapErrorResponse(502, undefined, noHeaders)).toEqual(server)
    expect(mapErrorResponse(404, undefined, noHeaders)).toEqual(server)
  })
})

const enc = new TextEncoder()

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${typeof data === 'string' ? data : JSON.stringify(data)}\n\n`
}

/** A streaming Response made of the given byte chunks. */
function streamResponse(chunks: Uint8Array[], status = 200): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(c)
      controller.close()
    },
  })
  return new Response(stream, { status, headers: { 'Content-Type': 'text/event-stream' } })
}

function recorder() {
  const calls: string[] = []
  const errors: AskError[] = []
  const handlers: AskHandlers = {
    onTrace: (e: TraceEvent) => calls.push(`trace:${e.node}`),
    onAnswer: (r: PipelineResult) => calls.push(`answer:${r.answer.text}`),
    onError: (e: AskError) => {
      calls.push(`error:${e.message}`)
      errors.push(e)
    },
  }
  return { calls, errors, handlers }
}

const trace = (node: string) => ({ type: 'node_start', node, message: '', data: {}, t_ms: 1 })
const result = { answer: { text: 'hi', citations: [], abstained: false }, contexts: [], trace: [] }
const fetchOf = (response: Response): FetchFn => () => Promise.resolve(response)
const ask = (f: FetchFn, h: AskHandlers, signal = new AbortController().signal) =>
  askStream('what is a graph?', 'baseline', signal, h, f)

describe('askStream', () => {
  it('posts JSON with the signal and calls handlers in order', async () => {
    let seen: { url: string; init: RequestInit } | undefined
    const { calls, handlers } = recorder()
    const body =
      sse('trace', trace('a')) + ': ping\n\n' + sse('trace', trace('b')) + sse('answer', result)
    await ask((url, init) => {
      seen = { url, init }
      return Promise.resolve(streamResponse([enc.encode(body)]))
    }, handlers)
    expect(calls).toEqual(['trace:a', 'trace:b', 'answer:hi'])
    expect(seen?.url).toBe('/api/ask')
    expect(seen?.init.method).toBe('POST')
    expect(JSON.parse(seen?.init.body as string)).toEqual({
      question: 'what is a graph?',
      pipeline: 'baseline',
    })
    expect(seen?.init.signal).toBeInstanceOf(AbortSignal)
  })

  it('works when the body is split into single bytes', async () => {
    const { calls, handlers } = recorder()
    const bytes = enc.encode(sse('trace', trace('é日')) + sse('answer', result))
    await ask(fetchOf(streamResponse([...bytes].map((b) => Uint8Array.of(b)))), handlers)
    expect(calls).toEqual(['trace:é日', 'answer:hi'])
  })

  it('stops at an error frame', async () => {
    const { calls, errors, handlers } = recorder()
    const body =
      sse('trace', trace('a')) + sse('error', { error: 'The model failed.' }) + sse('trace', trace('late'))
    await ask(fetchOf(streamResponse([enc.encode(body)])), handlers)
    expect(calls).toEqual(['trace:a', 'error:The model failed.'])
    expect(errors[0].kind).toBe('stream')
  })

  it('reports a stream with neither answer nor error', async () => {
    const { calls, handlers } = recorder()
    await ask(fetchOf(streamResponse([enc.encode(sse('trace', trace('a')))])), handlers)
    expect(calls).toEqual(['trace:a', 'error:The connection closed before an answer arrived.'])
  })

  it('uses a final frame that has no trailing blank line', async () => {
    const { calls, handlers } = recorder()
    const body = sse('trace', trace('a')) + 'event: answer\ndata: ' + JSON.stringify(result)
    await ask(fetchOf(streamResponse([enc.encode(body)])), handlers)
    expect(calls).toEqual(['trace:a', 'answer:hi'])
  })

  it('reports unreadable JSON and stops', async () => {
    const { calls, handlers } = recorder()
    const body = sse('trace', '{not json') + sse('answer', result)
    await ask(fetchOf(streamResponse([enc.encode(body)])), handlers)
    expect(calls).toEqual(['error:The server sent an unreadable response.'])
  })

  it('calls no handler when aborted before the response', async () => {
    const { calls, handlers } = recorder()
    const controller = new AbortController()
    controller.abort()
    await ask(
      () => Promise.reject(new DOMException('aborted', 'AbortError')),
      handlers,
      controller.signal,
    )
    expect(calls).toEqual([])
  })

  it('calls no handler when aborted mid-stream', async () => {
    const { calls, handlers } = recorder()
    const controller = new AbortController()
    const stream = new ReadableStream<Uint8Array>({
      pull(c) {
        controller.abort()
        c.error(new DOMException('aborted', 'AbortError'))
      },
    })
    await ask(fetchOf(new Response(stream, { status: 200 })), handlers, controller.signal)
    expect(calls).toEqual([])
  })

  it('reports a network TypeError as network', async () => {
    const { errors, handlers } = recorder()
    await ask(() => Promise.reject(new TypeError('Failed to fetch')), handlers)
    expect(errors).toEqual([{ kind: 'network', message: 'Could not reach the server.' }])
  })

  it('reports a stream that breaks mid-way as a dropped connection', async () => {
    const { calls, handlers } = recorder()
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode(sse('trace', trace('a'))))
        c.error(new TypeError('network error'))
      },
    })
    await ask(fetchOf(new Response(stream, { status: 200 })), handlers)
    expect(calls.at(-1)).toBe('error:The connection closed before an answer arrived.')
  })

  it('maps a 429 response with its body and header', async () => {
    const { errors, handlers } = recorder()
    const res = new Response(JSON.stringify({ error: 'Rate limit reached.', retry_after_s: 5 }), {
      status: 429,
      headers: { 'Retry-After': '5' },
    })
    await ask(fetchOf(res), handlers)
    expect(errors).toEqual([{ kind: 'rate', message: 'Rate limit reached.', retryAfterS: 5 }])
  })

  it('maps a non-JSON error body to server', async () => {
    const { errors, handlers } = recorder()
    await ask(fetchOf(new Response('<html>Bad gateway</html>', { status: 502 })), handlers)
    expect(errors).toEqual([{ kind: 'server', message: 'Something went wrong on the server.' }])
  })
})
