import { afterEach, describe, expect, it, vi } from 'vitest'
import { startCountdown } from './countdown'

afterEach(() => vi.useRealTimers())

describe('startCountdown', () => {
  it('ticks once per second and finishes at 0', () => {
    vi.useFakeTimers()
    const ticks: number[] = []
    let done = 0
    startCountdown(3, (n) => ticks.push(n), () => (done += 1))
    vi.advanceTimersByTime(999)
    expect(ticks).toEqual([])
    vi.advanceTimersByTime(1)
    expect(ticks).toEqual([2])
    vi.advanceTimersByTime(2000)
    expect(ticks).toEqual([2, 1, 0])
    expect(done).toBe(1)
    vi.advanceTimersByTime(5000)
    expect(ticks).toEqual([2, 1, 0])
  })

  it('can be cancelled', () => {
    vi.useFakeTimers()
    const ticks: number[] = []
    const cancel = startCountdown(5, (n) => ticks.push(n), () => undefined)
    vi.advanceTimersByTime(1000)
    cancel()
    vi.advanceTimersByTime(10000)
    expect(ticks).toEqual([4])
  })
})
