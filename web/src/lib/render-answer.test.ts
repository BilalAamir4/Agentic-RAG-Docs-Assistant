import { describe, expect, it } from 'vitest'
import { tokenizeAnswer } from './render-answer'
import type { AnswerBlock } from './render-answer'

const none = new Set<number>()

function parts(blocks: AnswerBlock[], i = 0) {
  const block = blocks[i]
  if (block.kind !== 'paragraph') throw new Error('not a paragraph')
  return block.parts
}

describe('tokenizeAnswer', () => {
  it('returns markup as plain text', () => {
    const blocks = tokenizeAnswer('<script>alert(1)</script>', none)
    expect(blocks).toEqual([
      { kind: 'paragraph', parts: [{ kind: 'text', text: '<script>alert(1)</script>' }] },
    ])
  })

  it('keeps a code fence verbatim, including [1]', () => {
    const blocks = tokenizeAnswer(
      'Before\n```python\nx = a[1]\n  y = [1]\n```\nAfter [1]',
      new Set([1]),
    )
    expect(blocks).toEqual([
      { kind: 'paragraph', parts: [{ kind: 'text', text: 'Before' }] },
      { kind: 'code', language: 'python', text: 'x = a[1]\n  y = [1]' },
      {
        kind: 'paragraph',
        parts: [
          { kind: 'text', text: 'After ' },
          { kind: 'citation', n: 1, linked: true },
        ],
      },
    ])
  })

  it('handles a fence without a language and an unterminated fence', () => {
    expect(tokenizeAnswer('```\nraw\n```', none)).toEqual([
      { kind: 'code', language: '', text: 'raw' },
    ])
    expect(tokenizeAnswer('```js\nlet a', none)).toEqual([
      { kind: 'code', language: 'js', text: 'let a' },
    ])
  })

  it('turns an inline backtick span into code, even around [1]', () => {
    expect(parts(tokenizeAnswer('Use `add_node` and `a[1]` here', new Set([1])))).toEqual([
      { kind: 'text', text: 'Use ' },
      { kind: 'code', text: 'add_node' },
      { kind: 'text', text: ' and ' },
      { kind: 'code', text: 'a[1]' },
      { kind: 'text', text: ' here' },
    ])
  })

  it('links a marker that has a source and not one that has none', () => {
    expect(parts(tokenizeAnswer('A [1] B [2].', new Set([1])))).toEqual([
      { kind: 'text', text: 'A ' },
      { kind: 'citation', n: 1, linked: true },
      { kind: 'text', text: ' B ' },
      { kind: 'citation', n: 2, linked: false },
      { kind: 'text', text: '.' },
    ])
  })

  it('leaves [100], [a], [0], [] and [01] as text', () => {
    const text = 'x [100] [a] [0] [] [01]'
    expect(parts(tokenizeAnswer(text, new Set([100, 0, 1])))).toEqual([{ kind: 'text', text }])
  })

  it('accepts 99 as a citation', () => {
    expect(parts(tokenizeAnswer('[99]', none))).toEqual([
      { kind: 'citation', n: 99, linked: false },
    ])
  })

  it('produces no citations when there are no markers', () => {
    const blocks = tokenizeAnswer('Plain answer with no markers.', new Set([1, 2]))
    expect(parts(blocks).some((p) => p.kind === 'citation')).toBe(false)
  })

  it('splits paragraphs on blank lines and keeps single newlines', () => {
    const blocks = tokenizeAnswer('line one\nline two\n\n\npara two', none)
    expect(blocks).toEqual([
      { kind: 'paragraph', parts: [{ kind: 'text', text: 'line one\nline two' }] },
      { kind: 'paragraph', parts: [{ kind: 'text', text: 'para two' }] },
    ])
  })

  it('handles CRLF input', () => {
    const blocks = tokenizeAnswer('a\r\nb\r\n\r\n```\r\ncode\r\n```\r\n', none)
    expect(blocks).toEqual([
      { kind: 'paragraph', parts: [{ kind: 'text', text: 'a\nb' }] },
      { kind: 'code', language: '', text: 'code' },
    ])
  })

  it('returns no blocks for empty text', () => {
    expect(tokenizeAnswer('', none)).toEqual([])
  })
})
