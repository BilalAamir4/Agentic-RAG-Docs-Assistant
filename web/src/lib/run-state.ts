/** Pure state of one ask run: the reducer behind useAskRun, and the rule for when Ask may submit. */
import type { PipelineResult, TraceEvent } from './api-types'
import type { AskError } from './ask'
import { MIN_QUESTION_CHARS } from './config'

export type RunStatus = 'idle' | 'running' | 'done' | 'failed' | 'stopped'

export interface RunState {
  status: RunStatus
  events: TraceEvent[]
  result: PipelineResult | null
  error: AskError | null
  /** Seconds until Ask is allowed again after a 429; 0 when not rate limited. */
  retryLeft: number
}

export type RunAction =
  | { type: 'start' }
  | { type: 'trace'; event: TraceEvent }
  | { type: 'answer'; result: PipelineResult }
  | { type: 'error'; error: AskError }
  | { type: 'stop' }
  | { type: 'tick'; secondsLeft: number }
  | { type: 'reset' }

export const IDLE_RUN: RunState = {
  status: 'idle',
  events: [],
  result: null,
  error: null,
  retryLeft: 0,
}

/** Apply one action. A stop only counts while a run is in progress. */
export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'start':
      return { ...IDLE_RUN, status: 'running' }
    case 'trace':
      return { ...state, events: [...state.events, action.event] }
    case 'answer':
      return { ...state, status: 'done', result: action.result }
    case 'error':
      return {
        ...state,
        status: 'failed',
        error: action.error,
        retryLeft: action.error.kind === 'rate' ? (action.error.retryAfterS ?? 0) : 0,
      }
    case 'stop':
      return state.status === 'running' ? { ...state, status: 'stopped' } : state
    case 'tick':
      return state.error?.kind === 'rate' ? { ...state, retryLeft: action.secondsLeft } : state
    case 'reset':
      return IDLE_RUN
  }
}

/**
 * True when Ask (the button and Ctrl+Enter) may submit: the trimmed question is long enough
 * and no run or rate-limit countdown is in progress.
 */
export function canSubmit(question: string, running: boolean, rateLimited: boolean): boolean {
  return question.trim().length >= MIN_QUESTION_CHARS && !running && !rateLimited
}
