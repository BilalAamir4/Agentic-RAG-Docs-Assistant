/**
 * Maps the data.outcome of a decision event to its tag and colour tone (D25).
 * The UI colours decisions from this field only, never from the message text.
 */

export type Tone = 'green' | 'amber' | 'red' | 'neutral'

export interface OutcomeStyle {
  /** Text shown in the badge. */
  tag: string
  tone: Tone
}

/**
 * Documented table: data.outcome -> tag and tone.
 *   "ok"    -> OK     green   (the step passed)
 *   "retry" -> RETRY  amber   (the pipeline goes around again)
 *   "stop"  -> STOP   red     (the pipeline stops or gives up here)
 *   "info"  -> INFO   neutral (a note; no verdict)
 * A missing value or any other value is treated as "info".
 */
export const OUTCOME_TABLE: Record<string, OutcomeStyle> = {
  ok: { tag: 'OK', tone: 'green' },
  retry: { tag: 'RETRY', tone: 'amber' },
  stop: { tag: 'STOP', tone: 'red' },
  info: { tag: 'INFO', tone: 'neutral' },
}

/** Style used for "info", a missing value and unknown values. */
export const FALLBACK_OUTCOME: OutcomeStyle = OUTCOME_TABLE.info

/** Look up the tag and tone for a data.outcome value of unknown type. */
export function outcomeStyle(outcome: unknown): OutcomeStyle {
  if (typeof outcome === 'string' && Object.hasOwn(OUTCOME_TABLE, outcome)) {
    return OUTCOME_TABLE[outcome]
  }
  return FALLBACK_OUTCOME
}

/** Tailwind classes per tone: a left border colour and badge colours for light and dark. */
export const TONE_CLASSES: Record<Tone, { border: string; badge: string }> = {
  green: {
    border: 'border-l-green-600 dark:border-l-green-500',
    badge:
      'border-green-600/40 bg-green-100 text-green-900 dark:border-green-500/40 dark:bg-green-950 dark:text-green-200',
  },
  amber: {
    border: 'border-l-amber-500 dark:border-l-amber-400',
    badge:
      'border-amber-600/40 bg-amber-100 text-amber-900 dark:border-amber-400/40 dark:bg-amber-950 dark:text-amber-200',
  },
  red: {
    border: 'border-l-red-600 dark:border-l-red-500',
    badge:
      'border-red-600/40 bg-red-100 text-red-900 dark:border-red-500/40 dark:bg-red-950 dark:text-red-200',
  },
  neutral: {
    border: 'border-l-neutral-400 dark:border-l-neutral-500',
    badge:
      'border-neutral-400/50 bg-neutral-100 text-neutral-800 dark:border-neutral-500/50 dark:bg-neutral-800 dark:text-neutral-200',
  },
}
