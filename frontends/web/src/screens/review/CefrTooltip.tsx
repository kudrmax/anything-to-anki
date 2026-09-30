import type { CEFRBreakdown, SourceVote } from '@/api/types'
import { Text, Tooltip } from '@/ui'
import css from './review.module.css'

const EFLLEX = 'EFLLex'
const MIN_SHARE = 0.05
const TOP_LEVELS = 2

function formatEFLLexDistribution(distribution: Record<string, number>): string {
  const entries = Object.entries(distribution)
    .filter(([, prob]) => prob > MIN_SHARE)
    .sort(([, a], [, b]) => b - a)
    .slice(0, TOP_LEVELS)
  return entries.map(([level, prob]) => `${level} ${Math.round(prob * 100)}%`).join(' ')
}

const levelOf = (vote: SourceVote): string =>
  vote.source_name === EFLLEX && vote.distribution ? formatEFLLexDistribution(vote.distribution) : (vote.level ?? '—')

interface CefrTooltipProps {
  breakdown: CEFRBreakdown
  cefrLevel: string
  anchor: HTMLElement
  onClose: () => void
}

export function CefrTooltip({ breakdown, cefrLevel, anchor, onClose }: CefrTooltipProps) {
  const decidingPriority = breakdown.decision_method === 'priority'
    ? breakdown.priority_votes.find(v => v.level === cefrLevel)
    : null
  const header = decidingPriority
    ? `${cefrLevel}  resolved by ${decidingPriority.source_name}`
    : `${cefrLevel}  vote of ${breakdown.votes.length} sources`
  const votes = [
    ...breakdown.priority_votes.map(vote => ({ vote, deciding: vote === decidingPriority })),
    ...breakdown.votes.map(vote => ({ vote, deciding: false })),
  ]

  return (
    <Tooltip anchor={anchor} onClose={onClose}>
      <div className={css.votesHeader}>{header}</div>
      {votes.map(({ vote, deciding }) => (
        <div key={vote.source_name} className={css.vote}>
          <Text tone="soft">{deciding ? '★ ' : ''}{vote.source_name}</Text>
          <Text mono>{levelOf(vote)}</Text>
        </div>
      ))}
    </Tooltip>
  )
}
