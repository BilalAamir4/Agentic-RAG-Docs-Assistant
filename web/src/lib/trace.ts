/** Helpers that read the loosely typed data of a trace event without trusting its shape. */
import type { RetrievalEventChunk } from './api-types'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * The chunk list of a retrieval event: data.chunks, keeping only entries that have a numeric
 * rank and score. Returns an empty list when data has no usable list (the row is then plain).
 */
export function retrievalChunks(data: Record<string, unknown>): RetrievalEventChunk[] {
  const raw = data.chunks
  if (!Array.isArray(raw)) return []
  const chunks: RetrievalEventChunk[] = []
  for (const item of raw) {
    if (!isRecord(item) || typeof item.rank !== 'number' || typeof item.score !== 'number') continue
    chunks.push({
      chunk_id: typeof item.chunk_id === 'string' ? item.chunk_id : undefined,
      url: typeof item.url === 'string' ? item.url : '',
      rank: item.rank,
      score: item.score,
      title: typeof item.title === 'string' ? item.title : '',
      heading_path: Array.isArray(item.heading_path)
        ? item.heading_path.filter((p): p is string => typeof p === 'string')
        : [],
    })
  }
  return chunks
}

/** The text shown for a chunk in the retrieval table: its title, else its heading path. */
export function chunkLabel(chunk: RetrievalEventChunk): string {
  return chunk.title !== '' ? chunk.title : chunk.heading_path.join(' › ')
}

/** data.reason of a decision event when it is a non-empty string. */
export function decisionReason(data: Record<string, unknown>): string | null {
  return typeof data.reason === 'string' && data.reason !== '' ? data.reason : null
}
