/** Owns the AbortController of the current run and turns askStream callbacks into actions. */
import type { PipelineName } from './api-types'
import { askStream } from './ask'
import type { FetchFn } from './ask'
import type { RunAction } from './run-state'

export class RunManager {
  private controller: AbortController | null = null
  private readonly dispatch: (action: RunAction) => void
  private readonly fetchFn: FetchFn | undefined

  constructor(dispatch: (action: RunAction) => void, fetchFn?: FetchFn) {
    this.dispatch = dispatch
    this.fetchFn = fetchFn
  }

  /** Abort any previous run, then start a new one. */
  start(question: string, pipeline: PipelineName): void {
    this.abort()
    const controller = new AbortController()
    this.controller = controller
    const live = (action: RunAction) => {
      if (this.controller === controller && !controller.signal.aborted) this.dispatch(action)
    }
    this.dispatch({ type: 'start' })
    void askStream(
      question,
      pipeline,
      controller.signal,
      {
        onTrace: (event) => live({ type: 'trace', event }),
        onAnswer: (result) => live({ type: 'answer', result }),
        onError: (error) => live({ type: 'error', error }),
      },
      this.fetchFn,
    )
  }

  /** The Stop button: abort the current run and record that the user stopped it. */
  stop(): void {
    if (this.controller === null || this.controller.signal.aborted) return
    this.abort()
    this.dispatch({ type: 'stop' })
  }

  /** Abort without a state change (a new run, unmount, page unload). */
  abort(): void {
    this.controller?.abort()
    this.controller = null
  }
}
