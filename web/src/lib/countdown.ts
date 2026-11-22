/** A once-per-second countdown without React, so it can be tested with fake timers. */

/** Milliseconds between ticks. */
export const COUNTDOWN_TICK_MS = 1000

/**
 * Call onTick(secondsLeft) once per second, starting from seconds - 1, and onDone() when it
 * reaches 0. Returns a function that cancels the countdown.
 */
export function startCountdown(
  seconds: number,
  onTick: (secondsLeft: number) => void,
  onDone: () => void,
): () => void {
  let left = Math.max(0, Math.ceil(seconds))
  const id = setInterval(() => {
    left -= 1
    onTick(left)
    if (left <= 0) {
      clearInterval(id)
      onDone()
    }
  }, COUNTDOWN_TICK_MS)
  return () => clearInterval(id)
}
