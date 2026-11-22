import { describe, expect, it } from 'vitest'
import type { PipelineResult, TraceEvent } from './api-types'
import { canSubmit, IDLE_RUN, runReducer } from './run-state'
import type { RunAction, RunState } from './run-state'

const event: TraceEvent = { type: 'node_start', node: 'retrieve', message: 'm', data: {}, t_ms: 1 }
const result = { answer: { text: 'a', citations: [], abstained: false } } as unknown as PipelineResult

function run(...actions: RunAction[]): RunState {
  return actions.reduce(runReducer, IDLE_RUN)
}

describe('runReducer', () => {
  it('start clears the previous run', () => {
    const state = run({ type: 'start' }, { type: 'trace', event }, { type: 'answer', result }, { type: 'start' })
    expect(state).toEqual({ ...IDLE_RUN, status: 'running' })
  })

  it('stop keeps the rows already received and marks the run stopped', () => {
    const state = run({ type: 'start' }, { type: 'trace', event }, { type: 'trace', event }, { type: 'stop' })
    expect(state.status).toBe('stopped')
    expect(state.events).toHaveLength(2)
    expect(state.result).toBeNull()
  })

  it('stop does nothing unless a run is in progress', () => {
    expect(run({ type: 'stop' }).status).toBe('idle')
    expect(run({ type: 'start' }, { type: 'answer', result }, { type: 'stop' }).status).toBe('done')
  })

  it('a rate-limit error sets the countdown and tick updates it', () => {
    const error = { kind: 'rate', message: 'm', retryAfterS: 5 } as const
    const state = run({ type: 'start' }, { type: 'error', error }, { type: 'tick', secondsLeft: 3 })
    expect(state).toMatchObject({ status: 'failed', retryLeft: 3 })
    expect(runReducer(state, { type: 'reset' })).toEqual(IDLE_RUN)
  })
})

describe('canSubmit (Ask and Ctrl+Enter)', () => {
  it('is ignored while running', () => {
    expect(canSubmit('a real question', true, false)).toBe(false)
  })

  it('is ignored during a countdown and for short questions', () => {
    expect(canSubmit('a real question', false, true)).toBe(false)
    expect(canSubmit('  ab  ', false, false)).toBe(false)
  })

  it('allows a long enough question when idle', () => {
    expect(canSubmit('  abc ', false, false)).toBe(true)
  })
})
