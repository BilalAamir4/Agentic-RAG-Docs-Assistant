import { describe, expect, it } from 'vitest'
import {
  formatCalls,
  formatMean,
  formatMetric,
  formatMs,
  formatPercent,
  formatRate,
  formatTokens,
  truncate,
} from './format'

describe('format', () => {
  it('formats rates with count and n', () => {
    expect(formatRate(38 / 42, 38, 42)).toBe('90.5% (38/42)')
    expect(formatRate(0, 0, 8)).toBe('0.0% (0/8)')
    expect(formatRate(1, 8, 8)).toBe('100.0% (8/8)')
  })
  it('rounds percentages at the edges', () => {
    expect(formatPercent(0)).toBe('0.0%')
    expect(formatPercent(1)).toBe('100.0%')
    expect(formatPercent(0.995)).toBe('99.5%')
    expect(formatPercent(0.9999)).toBe('100.0%')
  })
  it('formats means with two decimals and n', () => {
    expect(formatMean(0.9218917, 39)).toBe('0.92 (n=39)')
    expect(formatMean(0, 3)).toBe('0.00 (n=3)')
    expect(formatMean(1, 3)).toBe('1.00 (n=3)')
  })
  it('formats calls, tokens and ms', () => {
    expect(formatCalls(2.32)).toBe('2.3')
    expect(formatCalls(1)).toBe('1.0')
    expect(formatTokens(2333.56)).toBe('2,334')
    expect(formatTokens(999.4)).toBe('999')
    expect(formatTokens(1234567)).toBe('1,234,567')
    expect(formatTokens(0)).toBe('0')
    expect(formatMs(2207.5)).toBe('2.2 s')
    expect(formatMs(0)).toBe('0.0 s')
    expect(formatMs(49)).toBe('0.0 s')
  })
  it('shows n/a for null', () => {
    expect(formatRate(null, null, 0)).toBe('n/a')
    expect(formatMean(null, 0)).toBe('n/a')
    expect(formatCalls(null)).toBe('n/a')
    expect(formatTokens(null)).toBe('n/a')
    expect(formatMs(null)).toBe('n/a')
  })
  it('dispatches on kind and unit', () => {
    const base = { label: 'x', count: null, n: 50 }
    expect(formatMetric({ ...base, value: 4577.3, kind: 'number', unit: 'tokens' })).toBe('4,577')
    expect(formatMetric({ ...base, value: 3167, kind: 'number', unit: 'ms' })).toBe('3.2 s')
    expect(formatMetric({ ...base, value: null, kind: 'mean', unit: null })).toBe('n/a')
  })
  it('truncates long text', () => {
    expect(truncate('abc', 60)).toBe('abc')
    expect(truncate('a'.repeat(61), 60)).toHaveLength(60)
    expect(truncate('a'.repeat(61), 60).endsWith('…')).toBe(true)
  })
})
