import { describe, expect, it } from 'vitest'
import { outcomeStyle, TONE_CLASSES } from './outcome'

describe('outcomeStyle', () => {
  it('maps ok, retry, stop and info', () => {
    expect(outcomeStyle('ok')).toEqual({ tag: 'OK', tone: 'green' })
    expect(outcomeStyle('retry')).toEqual({ tag: 'RETRY', tone: 'amber' })
    expect(outcomeStyle('stop')).toEqual({ tag: 'STOP', tone: 'red' })
    expect(outcomeStyle('info')).toEqual({ tag: 'INFO', tone: 'neutral' })
  })

  it('treats a missing or unknown value as info', () => {
    expect(outcomeStyle(undefined)).toEqual({ tag: 'INFO', tone: 'neutral' })
    expect(outcomeStyle('weird')).toEqual({ tag: 'INFO', tone: 'neutral' })
    expect(outcomeStyle('toString')).toEqual({ tag: 'INFO', tone: 'neutral' })
    expect(outcomeStyle(3)).toEqual({ tag: 'INFO', tone: 'neutral' })
  })

  it('has border and badge classes with a dark variant for every tone', () => {
    for (const tone of ['green', 'amber', 'red', 'neutral'] as const) {
      expect(TONE_CLASSES[tone].border).toContain('dark:')
      expect(TONE_CLASSES[tone].badge).toContain('dark:')
    }
  })
})
