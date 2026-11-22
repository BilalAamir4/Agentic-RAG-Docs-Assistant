import { useEffect, useState } from 'react'
import type { PipelineInfo, PipelinesResponse } from '@/lib/api-types'
import { API_PIPELINES_PATH } from '@/lib/config'

/** Shown when GET /api/pipelines fails: the three names and labels, without descriptions. */
const FALLBACK_PIPELINES: PipelineInfo[] = [
  { name: 'baseline', label: 'Baseline RAG', description: '' },
  { name: 'corrective', label: 'Corrective RAG', description: '' },
  { name: 'self_rag', label: 'Self-RAG', description: '' },
]

export type PipelineState =
  | { status: 'loading' }
  | { status: 'ready'; pipelines: PipelineInfo[] }
  | { status: 'failed'; pipelines: PipelineInfo[] }

/** Load the pipeline list from the API once. */
export function usePipelines(): PipelineState {
  const [state, setState] = useState<PipelineState>({ status: 'loading' })
  useEffect(() => {
    let cancelled = false
    fetch(API_PIPELINES_PATH)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<PipelinesResponse>
      })
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', pipelines: data.pipelines })
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'failed', pipelines: FALLBACK_PIPELINES })
      })
    return () => {
      cancelled = true
    }
  }, [])
  return state
}
