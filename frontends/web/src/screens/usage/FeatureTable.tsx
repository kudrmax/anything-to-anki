import type { CSSProperties } from 'react'
import type { AIUsageFeature } from '@/api/types'
import { FEATURE_COLOR, FEATURE_LABEL, formatCount, formatTokens } from './usageFormat'
import css from './usage.module.css'

export function FeatureTable({ features }: { features: AIUsageFeature[] }) {
  return (
    <div className={css.table} role="table">
      <div className={`${css.tableRow} ${css.tableHead}`} role="row">
        <span role="columnheader">Function</span>
        <span role="columnheader">Requests</span>
        <span role="columnheader">Input</span>
        <span role="columnheader">Output</span>
        <span role="columnheader">Cache read</span>
        <span role="columnheader">Cache write</span>
        <span role="columnheader">Total</span>
        <span role="columnheader">Share</span>
      </div>
      {features.map(row => (
        <div key={row.feature} className={css.tableRow} role="row">
          <span className={css.featureName} role="cell">
            <span className={css.dot} style={{ '--segment-color': FEATURE_COLOR[row.feature] } as CSSProperties} />
            {FEATURE_LABEL[row.feature]}
          </span>
          <span role="cell">
            {formatCount(row.requests)}
            {row.failed_requests > 0 && <span className={css.failed}> · {formatCount(row.failed_requests)} failed</span>}
          </span>
          <span role="cell">{formatTokens(row.tokens.input)}</span>
          <span role="cell">{formatTokens(row.tokens.output)}</span>
          <span role="cell">{formatTokens(row.tokens.cache_read)}</span>
          <span role="cell">{formatTokens(row.tokens.cache_creation)}</span>
          <span className={css.total} role="cell">{formatTokens(row.tokens.total)}</span>
          <span className={css.share} role="cell">
            <span className={css.shareTrack}>
              <span
                className={css.shareFill}
                style={{ '--share': `${row.share_percent}%`, '--segment-color': FEATURE_COLOR[row.feature] } as CSSProperties}
              />
            </span>
            {row.share_percent}%
          </span>
        </div>
      ))}
    </div>
  )
}
