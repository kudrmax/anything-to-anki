import { useState, type CSSProperties } from 'react'
import type { AIUsageBucket } from '@/api/types'
import { FEATURE_COLOR, FEATURE_LABEL, formatDay, formatHour, formatTokens, labelledIndexes, niceCeiling } from './usageFormat'
import css from './usage.module.css'

const MAX_AXIS_LABELS = 7
const PERCENT = 100

interface UsageChartProps {
  buckets: AIUsageBucket[]
  bucketSize: 'hour' | 'day'
}

const percentOf = (value: number, whole: number): string => `${(value / whole) * PERCENT}%`

export function UsageChart({ buckets, bucketSize }: UsageChartProps) {
  const [hovered, setHovered] = useState<number | null>(null)
  const scale = niceCeiling(Math.max(0, ...buckets.map(bucket => bucket.total_tokens)))
  const labelled = labelledIndexes(buckets.length, MAX_AXIS_LABELS)
  const formatStart = bucketSize === 'hour' ? formatHour : formatDay
  const active = hovered === null ? null : buckets[hovered]

  return (
    <div className={css.chart}>
      <div className={css.axis} aria-hidden>
        <span>{formatTokens(scale)}</span>
        <span>{formatTokens(scale / 2)}</span>
        <span>0</span>
      </div>
      <div className={css.plot} onMouseLeave={() => setHovered(null)}>
        <span className={css.gridTop} />
        <span className={css.gridMid} />
        {buckets.map((bucket, index) => (
          <div
            key={bucket.start}
            className={hovered === index ? `${css.column} ${css.columnOn}` : css.column}
            tabIndex={0}
            aria-label={`${formatStart(bucket.start)}: ${formatTokens(bucket.total_tokens)} tokens`}
            onMouseEnter={() => setHovered(index)}
            onFocus={() => setHovered(index)}
            onBlur={() => setHovered(null)}
          >
            {bucket.features.filter(part => part.tokens > 0).map(part => (
              <span
                key={part.feature}
                className={css.segment}
                style={{ '--segment-h': percentOf(part.tokens, scale), '--segment-color': FEATURE_COLOR[part.feature] } as CSSProperties}
              />
            ))}
          </div>
        ))}
        {active && hovered !== null && (
          <div
            className={hovered < buckets.length / 2 ? css.pop : `${css.pop} ${css.popLeft}`}
            style={{ '--pop-x': percentOf(hovered + 0.5, buckets.length) } as CSSProperties}
            role="tooltip"
          >
            <div className={css.popHead}>
              <span>{formatStart(active.start)}</span>
              <b>{formatTokens(active.total_tokens)}</b>
            </div>
            {active.features.filter(part => part.tokens > 0).map(part => (
              <div key={part.feature} className={css.popRow}>
                <span className={css.dot} style={{ '--segment-color': FEATURE_COLOR[part.feature] } as CSSProperties} />
                <span className={css.popName}>{FEATURE_LABEL[part.feature]}</span>
                <span>{formatTokens(part.tokens)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className={css.ticks} aria-hidden>
        {buckets.map((bucket, index) => (
          <span key={bucket.start}>{labelled.has(index) ? formatStart(bucket.start) : ''}</span>
        ))}
      </div>
    </div>
  )
}
