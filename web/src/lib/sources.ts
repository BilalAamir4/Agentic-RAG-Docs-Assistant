/** Builds the Sources list from a PipelineResult (D20: Sources stand on their own). */
import type { PipelineResult } from './api-types'

/** Prefix of the chunk_id of a web-search result. */
export const WEB_CHUNK_PREFIX = 'web-'

export interface SourceEntry {
  /** The excerpt number the model saw: the 1-based position in result.contexts. */
  n: number
  chunkId: string
  title: string
  headingPath: string[]
  url: string
  isWeb: boolean
}

export interface SourcesResult {
  sources: SourceEntry[]
  /** Citations whose chunk_id is not in result.contexts. */
  skipped: number
}

/**
 * List the cited sources in citation order, one entry per chunk. A citation matches
 * contexts[i].chunk.chunk_id and its excerpt number is i + 1. A citation with no matching
 * context is skipped and counted.
 */
export function buildSources(result: PipelineResult): SourcesResult {
  const sources: SourceEntry[] = []
  const seen = new Set<string>()
  let skipped = 0
  for (const citation of result.answer.citations) {
    if (seen.has(citation.chunk_id)) continue
    const index = result.contexts.findIndex((c) => c.chunk.chunk_id === citation.chunk_id)
    if (index === -1) {
      skipped += 1
      continue
    }
    seen.add(citation.chunk_id)
    const chunk = result.contexts[index].chunk
    sources.push({
      n: index + 1,
      chunkId: chunk.chunk_id,
      title: chunk.title,
      headingPath: chunk.heading_path,
      url: chunk.url,
      isWeb: chunk.chunk_id.startsWith(WEB_CHUNK_PREFIX),
    })
  }
  return { sources, skipped }
}
