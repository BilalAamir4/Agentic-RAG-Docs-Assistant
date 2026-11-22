import { describe, expect, it } from 'vitest'
import { SseParser } from './sse'
import type { SseFrame } from './sse'

const SAMPLE =
  ': ping\n\n' +
  'event: trace\nid: 7\nretry: 100\ndata: {"node":"é日本"}\n\n' +
  'data: one\ndata: two\n\n' +
  'event: answer\ndata:no-space\n\n'

function parseAll(chunks: string[]): SseFrame[] {
  const parser = new SseParser()
  const frames: SseFrame[] = []
  for (const chunk of chunks) frames.push(...parser.push(chunk))
  frames.push(...parser.end())
  return frames
}

const EXPECTED: SseFrame[] = [
  { type: 'comment', event: '', data: 'ping' },
  { type: 'event', event: 'trace', data: '{"node":"é日本"}' },
  { type: 'event', event: 'message', data: 'one\ntwo' },
  { type: 'event', event: 'answer', data: 'no-space' },
]

describe('SseParser', () => {
  it('parses a whole stream', () => {
    expect(parseAll([SAMPLE])).toEqual(EXPECTED)
  })

  it('gives the same frames when split at every position', () => {
    for (let i = 0; i <= SAMPLE.length; i++) {
      expect(parseAll([SAMPLE.slice(0, i), SAMPLE.slice(i)])).toEqual(EXPECTED)
    }
  })

  it('gives the same frames one character at a time', () => {
    expect(parseAll([...SAMPLE])).toEqual(EXPECTED)
  })

  it('accepts CRLF, including a split CRLF pair', () => {
    const crlf = SAMPLE.replace(/\n/g, '\r\n')
    expect(parseAll([crlf])).toEqual(EXPECTED)
    for (let i = 0; i <= crlf.length; i++) {
      expect(parseAll([crlf.slice(0, i), crlf.slice(i)])).toEqual(EXPECTED)
    }
  })

  it('accepts bare CR line ends', () => {
    const cr = SAMPLE.replace(/\n/g, '\r')
    expect(parseAll([cr])).toEqual(EXPECTED)
    expect(parseAll([...cr])).toEqual(EXPECTED)
  })

  it('returns comment frames so the caller can ignore them', () => {
    const frames = new SseParser().push(': keep-alive\n\n')
    expect(frames).toEqual([{ type: 'comment', event: '', data: 'keep-alive' }])
  })

  it('joins multi-line data with newlines and strips one space only', () => {
    const frames = new SseParser().push('data:  a\ndata: b\ndata\n\n')
    expect(frames).toEqual([{ type: 'event', event: 'message', data: ' a\nb\n' }])
  })

  it('returns a final frame that has no trailing blank line from end()', () => {
    const parser = new SseParser()
    expect(parser.push('event: answer\ndata: {"a":1}\n')).toEqual([])
    expect(parser.end()).toEqual([{ type: 'event', event: 'answer', data: '{"a":1}' }])
    expect(parser.end()).toEqual([])
  })

  it('ignores unknown fields and empty blocks', () => {
    expect(new SseParser().push('foo: bar\n\n\n\n')).toEqual([])
  })

  it('keeps non-ASCII text intact across byte-split chunks', () => {
    const bytes = new TextEncoder().encode('data: héllo 日本語 🙂\n\n')
    for (let i = 0; i <= bytes.length; i++) {
      const decoder = new TextDecoder()
      const parser = new SseParser()
      const frames = [
        ...parser.push(decoder.decode(bytes.slice(0, i), { stream: true })),
        ...parser.push(decoder.decode(bytes.slice(i), { stream: true })),
        ...parser.end(),
      ]
      expect(frames).toEqual([{ type: 'event', event: 'message', data: 'héllo 日本語 🙂' }])
    }
  })
})
