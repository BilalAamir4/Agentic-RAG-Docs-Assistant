import { describe, expect, it } from 'vitest'
import { chunkLabel, decisionReason, retrievalChunks } from './trace'

describe('retrievalChunks', () => {
  it('reads the baseline shape (no chunk_id)', () => {
    const chunks = retrievalChunks({
      mode: 'hybrid',
      chunks: [{ rank: 1, title: 'Graphs', heading_path: ['A', 'B'], url: 'u', score: 0.1234 }],
    })
    expect(chunks).toEqual([
      { chunk_id: undefined, url: 'u', rank: 1, score: 0.1234, title: 'Graphs', heading_path: ['A', 'B'] },
    ])
  })

  it('keeps chunk_id when present and drops malformed entries', () => {
    const chunks = retrievalChunks({
      chunks: [{ chunk_id: 'c1', rank: 2, score: 1 }, { rank: 'x', score: 1 }, null, 'text'],
    })
    expect(chunks).toHaveLength(1)
    expect(chunks[0]).toMatchObject({ chunk_id: 'c1', title: '', heading_path: [] })
  })

  it('returns an empty list when there is no list', () => {
    expect(retrievalChunks({})).toEqual([])
    expect(retrievalChunks({ chunks: 'no' })).toEqual([])
  })
})

describe('chunkLabel and decisionReason', () => {
  it('prefers the title, then the heading path', () => {
    expect(chunkLabel({ url: '', rank: 1, score: 0, title: 'T', heading_path: ['A'] })).toBe('T')
    expect(chunkLabel({ url: '', rank: 1, score: 0, title: '', heading_path: ['A', 'B'] })).toBe('A › B')
  })

  it('reads a string reason only', () => {
    expect(decisionReason({ reason: 'because' })).toBe('because')
    expect(decisionReason({ reason: '' })).toBeNull()
    expect(decisionReason({ reason: 3 })).toBeNull()
  })
})
