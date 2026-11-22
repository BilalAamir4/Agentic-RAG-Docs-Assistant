import { useCallback, useEffect, useReducer, useState } from 'react'
import type { PipelineName } from '@/lib/api-types'
import { startCountdown } from '@/lib/countdown'
import { RunManager } from '@/lib/run-manager'
import { IDLE_RUN, runReducer } from '@/lib/run-state'
import type { RunState } from '@/lib/run-state'

/**
 * Owns one ask run at a time. start() aborts the previous run (unmount and page unload use the
 * same path), clears the trace, answer and error, then streams the new one. stop() aborts the
 * current run and keeps the rows received so far. After a 429 it counts retryLeft down once per
 * second and clears the error when it reaches 0.
 */
export function useAskRun(): {
  state: RunState
  start: (q: string, p: PipelineName) => void
  stop: () => void
} {
  const [state, dispatch] = useReducer(runReducer, IDLE_RUN)
  const [manager] = useState(() => new RunManager(dispatch))
  const retryAfterS = state.error?.kind === 'rate' ? state.error.retryAfterS : undefined

  useEffect(() => {
    const abortOnUnload = () => manager.abort()
    window.addEventListener('pagehide', abortOnUnload)
    return () => {
      window.removeEventListener('pagehide', abortOnUnload)
      manager.abort()
    }
  }, [manager])

  useEffect(() => {
    if (retryAfterS === undefined) return undefined
    return startCountdown(
      retryAfterS,
      (secondsLeft) => dispatch({ type: 'tick', secondsLeft }),
      () => dispatch({ type: 'reset' }),
    )
  }, [retryAfterS, state.error])

  const start = useCallback((q: string, p: PipelineName) => manager.start(q, p), [manager])
  const stop = useCallback(() => manager.stop(), [manager])
  return { state, start, stop }
}
