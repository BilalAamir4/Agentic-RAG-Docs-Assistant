import type { ResultMetric } from './api-types'

/** Text shown for a missing value. */
export const NOT_AVAILABLE = 'n/a'

/** Format a 0 to 1 fraction as a percent with one decimal, for example "90.5%". */
export function formatPercent(fraction: number): string {
  return `${(fraction * 100).toFixed(1)}%`
}

/** Format a rate: "90.5% (38/42)". A null value gives "n/a". */
export function formatRate(value: number | null, count: number | null, n: number): string {
  if (value === null) return NOT_AVAILABLE
  return count === null ? formatPercent(value) : `${formatPercent(value)} (${count}/${n})`
}

/** Format a mean: two decimals plus the sample size, "0.92 (n=39)". */
export function formatMean(value: number | null, n: number): string {
  if (value === null) return NOT_AVAILABLE
  return `${value.toFixed(2)} (n=${n})`
}

/** Format a mean call count with one decimal. */
export function formatCalls(value: number | null): string {
  return value === null ? NOT_AVAILABLE : value.toFixed(1)
}

/** Format a token count: rounded, with thousands separators. */
export function formatTokens(value: number | null): string {
  return value === null ? NOT_AVAILABLE : Math.round(value).toLocaleString('en-US')
}

/** Format milliseconds as seconds with one decimal, "2.2 s". */
export function formatMs(value: number | null): string {
  return value === null ? NOT_AVAILABLE : `${(value / 1000).toFixed(1)} s`
}

/** Format any results.json metric according to its kind and unit. */
export function formatMetric(metric: ResultMetric): string {
  if (metric.kind === 'rate') return formatRate(metric.value, metric.count, metric.n)
  if (metric.kind === 'mean') return formatMean(metric.value, metric.n)
  if (metric.unit === 'calls') return formatCalls(metric.value)
  if (metric.unit === 'tokens') return formatTokens(metric.value)
  if (metric.unit === 'ms') return formatMs(metric.value)
  return metric.value === null ? NOT_AVAILABLE : String(metric.value)
}

/** Shorten text to at most max characters, ending with an ellipsis when cut. */
export function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`
}
