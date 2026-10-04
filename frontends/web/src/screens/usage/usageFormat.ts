import type { AIFeature, UsagePeriod } from '@/api/types'

export const FEATURE_LABEL: Record<AIFeature, string> = {
  meaning_batch: 'Meanings',
  meaning_single: 'Single meaning',
  meaning_follow_up: 'Meaning follow-up',
  phrase_polish: 'Phrase polish',
  topic_targets: 'Topic targets',
}

export const FEATURE_COLOR: Record<AIFeature, string> = {
  meaning_batch: 'var(--usage-1)',
  phrase_polish: 'var(--usage-2)',
  topic_targets: 'var(--usage-3)',
  meaning_single: 'var(--usage-4)',
  meaning_follow_up: 'var(--usage-5)',
}

export const PERIOD_OPTIONS: { value: UsagePeriod; label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: 'all', label: 'All time' },
]

const PREVIOUS_PERIOD: Record<UsagePeriod, string> = {
  today: 'the same time yesterday',
  '7d': 'previous 7 days',
  '30d': 'previous 30 days',
  all: '',
}

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
const whole = new Intl.NumberFormat('en')
const dayFormat = new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' })
const hourFormat = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })

export const formatTokens = (tokens: number): string => compact.format(tokens)
export const formatCount = (count: number): string => whole.format(count)
export const formatDay = (iso: string): string => dayFormat.format(new Date(iso))
export const formatHour = (iso: string): string => hourFormat.format(new Date(iso))

export function formatChange(changePercent: number, period: UsagePeriod): string {
  const sign = changePercent > 0 ? '+' : changePercent < 0 ? '−' : '±'
  return `${sign}${Math.abs(changePercent)}% vs ${PREVIOUS_PERIOD[period]}`
}

/** Верх шкалы графика: ближайшее сверху «круглое» число вида 1, 2, 5 × 10ⁿ. */
export function niceCeiling(value: number): number {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const step = [1, 2, 5, 10].find(multiplier => multiplier * magnitude >= value) ?? 10
  return step * magnitude
}

/** Какие столбцы подписать по оси X: первый, последний и равномерно между ними. */
export function labelledIndexes(count: number, maxLabels: number): Set<number> {
  if (count <= maxLabels) return new Set(Array.from({ length: count }, (_, i) => i))
  const last = count - 1
  const step = Math.ceil(last / (maxLabels - 1))
  const indexes: number[] = []
  for (let i = 0; i < last; i += step) indexes.push(i)
  if (last - indexes[indexes.length - 1] < step / 2) indexes.pop()
  indexes.push(last)
  return new Set(indexes)
}
