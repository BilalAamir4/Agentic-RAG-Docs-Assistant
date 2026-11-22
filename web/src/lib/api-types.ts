/** TypeScript types for the payloads of docs/progress/M12-api.md, field for field. */

/** Pipeline names accepted by POST /api/ask. */
export type PipelineName = 'baseline' | 'corrective' | 'self_rag'

/** One entry of GET /api/pipelines. */
export interface PipelineInfo {
  name: PipelineName
  label: string
  description: string
}

/** Body of GET /api/pipelines. */
export interface PipelinesResponse {
  pipelines: PipelineInfo[]
}

/** Body of POST /api/ask. */
export interface AskRequest {
  question: string
  pipeline: PipelineName
}

/** Trace event types. "answer" and "error" are never sent as `trace` SSE events. */
export type TraceEventType =
  | 'node_start'
  | 'node_end'
  | 'decision'
  | 'retrieval'
  | 'answer'
  | 'error'

/** SSE event `trace`; also the items of PipelineResult.trace. t_ms is ms since the pipeline started. */
export interface TraceEvent {
  type: TraceEventType
  node: string
  message: string
  data: Record<string, unknown>
  t_ms: number
}

/** Value of data.outcome on every decision event (D25). */
export type DecisionOutcome = 'ok' | 'retry' | 'stop' | 'info'

/** One chunk in a retrieval event's data.chunks. The baseline omits chunk_id. */
export interface RetrievalEventChunk {
  chunk_id?: string
  url: string
  rank: number
  score: number
  title: string
  heading_path: string[]
}

/** Documentation chunk (ragdocs.schemas.Chunk). */
export interface Chunk {
  chunk_id: string
  doc_path: string
  url: string
  title: string
  heading_path: string[]
  anchor: string
  text: string
  embed_text: string
  n_tokens: number
  has_code: boolean
  source_commit: string
}

/** One context given to the generator (ragdocs.schemas.RetrievedChunk). */
export interface RetrievedChunk {
  chunk: Chunk
  score: number
  rank: number
  retriever: string
}

/** A citation; chunk_id matches contexts[i].chunk.chunk_id. */
export interface Citation {
  chunk_id: string
  url: string
}

/** The answer text and its citations. */
export interface Answer {
  text: string
  citations: Citation[]
  abstained: boolean
}

/** SSE event `answer`. diagnostics is present only when non-empty. */
export interface PipelineResult {
  question: string
  pipeline: string
  answer: Answer
  contexts: RetrievedChunk[]
  trace: TraceEvent[]
  llm_calls: number
  latency_ms: number
  used_web: boolean
  diagnostics?: Record<string, unknown>
}

/** SSE event `error`, and the JSON body of every non-200 /api/ask response. */
export interface ApiError {
  error: string
  /** Only on 429 (also sent as the Retry-After header). */
  retry_after_s?: number
}

export type MetricKind = 'rate' | 'mean' | 'number'

/** One metric of one pipeline in results.json. */
export interface ResultMetric {
  label: string
  value: number | null
  count: number | null
  n: number
  kind: MetricKind
  unit: 'calls' | 'tokens' | 'ms' | null
}

/** One pipeline column of results.json. */
export interface ResultPipeline {
  name: PipelineName
  label: string
  run_dir: string
  metrics: Record<string, ResultMetric>
}

/** The whole results.json file. */
export interface ResultsFile {
  generated_on: string
  n_questions: number
  eval_set_sha256: string
  pipelines: ResultPipeline[]
}

/** One entry of examples.json. */
export interface ExampleQuestion {
  id: string
  category: 'single' | 'multi' | 'version' | 'unanswerable'
  label: string
  question: string
}
