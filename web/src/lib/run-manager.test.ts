import { describe, expect, it } from 'vitest'
import type { FetchFn } from './ask'
import { RunManager } from './run-manager'
import { IDLE_RUN, runReducer } from './run-state'
import type { RunAction } from './run-state'

const enc = new TextEncoder()
const frame = (node: string) =>
  enc.encode(
    `event: trace\ndata: ${JSON.stringify({ type: 'node_start', node, message: '', data: {}, t_ms: 1 })}\n\n`,
  )

/** A fetch whose stream stays open; the test pushes frames into it. */
function openStream() {
  const controllers: ReadableStreamDefaultController<Uint8Array>[] = []
  const signals: AbortSignal[] = []
  const fetchFn: FetchFn = (_url, init) => {
    signals.push(init.signal as AbortSignal)
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        controllers.push(c)
      },
    })
    return Promise.resolve(new Response(body, { status: 200 }))
  }
  /** Push bytes into the stream of the n-th request (default: the latest). */
  const push = (b: Uint8Array, n = controllers.length - 1) => controllers[n].enqueue(b)
  return { fetchFn, signals, push }
}

/** Let queued promise callbacks (the stream reader) run; no timers. */
const settle = async () => {
  for (let i = 0; i < 50; i++) await Promise.resolve()
}

describe('RunManager', () => {
  it('stop aborts the signal and records the stop after the rows received', async () => {
    const { fetchFn, signals, push } = openStream()
    const actions: RunAction[] = []
    const manager = new RunManager((a) => actions.push(a), fetchFn)
    manager.start('a question', 'self_rag')
    await settle()
    push(frame('one'))
    push(frame('two'))
    await settle()
    manager.stop()
    expect(signals[0].aborted).toBe(true)
    const state = actions.reduce(runReducer, IDLE_RUN)
    expect(state.status).toBe('stopped')
    expect(state.events.map((e) => e.node)).toEqual(['one', 'two'])
  })

  it('fires no handler after abort', async () => {
    const { fetchFn, push } = openStream()
    const actions: RunAction[] = []
    const manager = new RunManager((a) => actions.push(a), fetchFn)
    manager.start('a question', 'baseline')
    await settle()
    push(frame('one'))
    await settle()
    manager.stop()
    const before = actions.length
    push(frame('late'))
    push(enc.encode('event: answer\ndata: {"answer":{"text":"x"}}\n\n'))
    await settle()
    expect(actions).toHaveLength(before)
    expect(actions.at(-1)).toEqual({ type: 'stop' })
  })

  it('a new start aborts the previous run and ignores its rows', async () => {
    const first = openStream()
    const actions: RunAction[] = []
    const manager = new RunManager((a) => actions.push(a), first.fetchFn)
    manager.start('first question', 'baseline')
    await settle()
    manager.start('second question', 'baseline')
    expect(first.signals[0].aborted).toBe(true)
    first.push(frame('stale'), 0)
    await settle()
    expect(actions.filter((a) => a.type === 'trace')).toEqual([])
  })

  it('stop with no run does nothing', () => {
    const actions: RunAction[] = []
    new RunManager((a) => actions.push(a)).stop()
    expect(actions).toEqual([])
  })
})
