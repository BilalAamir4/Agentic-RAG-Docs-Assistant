/** Incremental parser for a text/event-stream body (WHATWG "Server-sent events" framing). */

/** One parsed frame. A comment frame carries the comment text in data and is meant to be ignored. */
export interface SseFrame {
  /** "comment" for a line starting with ":", otherwise "event". */
  type: 'event' | 'comment'
  /** The event name; "message" when the frame has no "event:" line. Empty for comments. */
  event: string
  /** Joined "data:" lines (with \n), or the comment text. */
  data: string
}

/** Event name used when a frame has no "event:" line. */
export const DEFAULT_EVENT_NAME = 'message'

/** Remove one leading space, as the SSE format requires. */
function stripOneSpace(value: string): string {
  return value.startsWith(' ') ? value.slice(1) : value
}

/** Turn one blank-line-terminated block of lines into zero or more frames. */
function parseBlock(block: string): SseFrame[] {
  const frames: SseFrame[] = []
  const dataLines: string[] = []
  let event = DEFAULT_EVENT_NAME
  let sawField = false
  for (const line of block.split('\n')) {
    if (line === '') continue
    if (line.startsWith(':')) {
      frames.push({ type: 'comment', event: '', data: stripOneSpace(line.slice(1)) })
      continue
    }
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    const value = colon === -1 ? '' : stripOneSpace(line.slice(colon + 1))
    if (field === 'event') {
      event = value
      sawField = true
    } else if (field === 'data') {
      dataLines.push(value)
      sawField = true
    }
    // Any other field (id, retry, unknown) is ignored.
  }
  if (sawField) frames.push({ type: 'event', event, data: dataLines.join('\n') })
  return frames
}

/**
 * Splits a stream of text chunks into frames. Frames end at a blank line; the line terminators
 * \n, \r\n and \r are all accepted, including when a \r\n pair is split across two chunks.
 * A frame is returned as soon as its blank line has arrived; end() returns whatever is left.
 */
export class SseParser {
  private buffer = ''
  private pendingCr = false

  /** Add a chunk of decoded text and return the frames that are now complete. */
  push(chunk: string): SseFrame[] {
    let text = chunk
    if (this.pendingCr && text.startsWith('\n')) text = text.slice(1)
    if (text.length > 0 || chunk.length > 0) this.pendingCr = text.endsWith('\r')
    this.buffer += text.replace(/\r\n?/g, '\n')
    const frames: SseFrame[] = []
    for (;;) {
      const end = this.buffer.indexOf('\n\n')
      if (end === -1) break
      frames.push(...parseBlock(this.buffer.slice(0, end)))
      this.buffer = this.buffer.slice(end + 2)
    }
    return frames
  }

  /** Return the final frame, if the stream ended without a trailing blank line. */
  end(): SseFrame[] {
    const rest = this.buffer
    this.buffer = ''
    this.pendingCr = false
    return parseBlock(rest)
  }
}
