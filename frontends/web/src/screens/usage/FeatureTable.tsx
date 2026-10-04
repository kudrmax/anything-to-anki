import type { CSSProperties } from 'react'
import type { AIUsageFeature } from '@/api/types'
import { FEATURE_COLOR, FEATURE_LABEL, formatCount, formatPercent, formatTokens } from './usageFormat'
import css from './usage.module.css'

export function FeatureTable({ features }: { features: AIUsageFeature[] }) {
  return (
    <div className={css.table} role="table">
      <div className={`${css.tableRow} ${css.tableHead}`} role="row">
        <span role="columnheader">What AI did</span>
        <span role="columnheader" title="How many times this was run">Runs</span>
        <span role="columnheader" title="Instructions and text sent to the AI">Sent</span>
        <span role="columnheader" title="Text the AI wrote back">Answer</span>
        <span role="columnheader" title="Sent + answer">Tokens</span>
        <span role="columnheader">Of all tokens</span>
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
          <span role="cell">{formatTokens(row.tokens.sent)}</span>
          <span role="cell">{formatTokens(row.tokens.answer)}</span>
          <span className={css.total} role="cell">{formatTokens(row.tokens.total)}</span>
          <span className={css.share} role="cell">
            <span className={css.shareTrack}>
              <span
                className={css.shareFill}
                style={{ '--share': `${row.share_percent}%`, '--segment-color': FEATURE_COLOR[row.feature] } as CSSProperties}
              />
            </span>
            {formatPercent(row.share_percent)}
          </span>
        </div>
      ))}
    </div>
  )
}
