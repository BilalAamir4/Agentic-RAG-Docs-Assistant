import { describe, expect, it } from 'vitest'
import type { PipelineResult, RetrievedChunk } from './api-types'
import { buildSources } from './sources'

function ctx(id: string, title: string): RetrievedChunk {
  return {
    chunk: {
      chunk_id: id,
      doc_path: `${id}.md`,
      url: `https://docs.example/${id}`,
      title,
      heading_path: ['Guide', title],
      anchor: '',
      text: '',
      embed_text: '',
      n_tokens: 1,
      has_code: false,
      source_commit: 'abc',
    },
    score: 0.5,
    rank: 1,
    retriever: 'hybrid',
  }
}

function result(citationIds: string[], contexts: RetrievedChunk[]): PipelineResult {
  return {
    question: 'q',
    pipeline: 'baseline',
    answer: {
      text: 'a',
      citations: citationIds.map((id) => ({ chunk_id: id, url: `u/${id}` })),
      abstained: false,
    },
    contexts,
    trace: [],
    llm_calls: 1,
    latency_ms: 1000,
    used_web: false,
  }
}

const contexts = [ctx('c1', 'One'), ctx('c2', 'Two'), ctx('web-3', 'Three')]

describe('buildSources', () => {
  it('lists sources in citation order with the excerpt number the model saw', () => {
    const { sources, skipped } = buildSources(result(['c2', 'c1'], contexts))
    expect(sources.map((s) => [s.n, s.title])).toEqual([
      [2, 'Two'],
      [1, 'One'],
    ])
    expect(sources[0]).toMatchObject({
      url: 'https://docs.example/c2',
      headingPath: ['Guide', 'Two'],
      isWeb: false,
    })
    expect(skipped).toBe(0)
  })

  it('removes duplicates', () => {
    const { sources } = buildSources(result(['c1', 'c1', 'c2', 'c1'], contexts))
    expect(sources.map((s) => s.n)).toEqual([1, 2])
  })

  it('marks web results', () => {
    const { sources } = buildSources(result(['web-3'], contexts))
    expect(sources).toHaveLength(1)
    expect(sources[0]).toMatchObject({ n: 3, isWeb: true })
  })

  it('skips and counts a citation whose context is missing', () => {
    const { sources, skipped } = buildSources(result(['c1', 'gone', 'gone2'], contexts))
    expect(sources.map((s) => s.n)).toEqual([1])
    expect(skipped).toBe(2)
  })

  it('returns nothing when there are no citations', () => {
    expect(buildSources(result([], contexts))).toEqual({ sources: [], skipped: 0 })
  })
})
