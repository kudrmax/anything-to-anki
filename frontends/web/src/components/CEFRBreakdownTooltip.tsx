import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CEFRBreakdown, SourceVote } from '@/api/types'

function formatEFLLexDistribution(distribution: Record<string, number>): string {
  const entries = Object.entries(distribution)
    .filter(([, prob]) => prob > 0.05)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 2)
  return entries.map(([level, prob]) => `${level} ${Math.round(prob * 100)}%`).join(' ')
}

function VoteRow({ vote, isPriority }: { vote: SourceVote; isPriority: boolean }) {
  const isEFLLex = vote.source_name === 'EFLLex'
  const levelDisplay = isEFLLex && vote.distribution
    ? formatEFLLexDistribution(vote.distribution)
    : (vote.level ?? '\u2014')

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      gap: '12px',
      padding: '2px 0',
      fontSize: '12px',
      fontFamily: 'var(--font-mono, monospace)',
    }}>
      <span style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
        {isPriority ? '\u2605 ' : '  '}{vote.source_name}
      </span>
      <span style={{
        fontWeight: vote.level ? 600 : 400,
        color: vote.level ? 'var(--text-primary)' : 'var(--text-tertiary)',
        whiteSpace: 'nowrap',
      }}>
        {levelDisplay}
      </span>
    </div>
  )
}

interface CEFRBreakdownTooltipProps {
  breakdown: CEFRBreakdown
  cefrLevel: string
  anchorEl: HTMLElement
  onClose: () => void
}

export function CEFRBreakdownTooltip({ breakdown, cefrLevel, anchorEl, onClose }: CEFRBreakdownTooltipProps) {
  const [pos, setPos] = useState({ top: 0, left: 0 })

  useEffect(() => {
    const rect = anchorEl.getBoundingClientRect()
    const tooltipWidth = 280
    let left = rect.right - tooltipWidth
    if (left < 8) left = 8
    setPos({ top: rect.bottom + 6, left })
  }, [anchorEl])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (!anchorEl.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [anchorEl, onClose])

  const headerText = breakdown.decision_method === 'priority' && breakdown.priority_vote
    ? `${cefrLevel}  resolved by ${breakdown.priority_vote.source_name}`
    : `${cefrLevel}  vote of ${breakdown.votes.length} sources`

  const allVotes: { vote: SourceVote; isPriority: boolean }[] = []
  if (breakdown.priority_vote) {
    allVotes.push({ vote: breakdown.priority_vote, isPriority: breakdown.decision_method === 'priority' })
  }
  for (const v of breakdown.votes) {
    allVotes.push({ vote: v, isPriority: false })
  }

  return createPortal(
    <div style={{
      position: 'fixed',
      top: pos.top,
      left: pos.left,
      width: 280,
      padding: '10px 12px',
      background: 'var(--card-bg, var(--bg-secondary))',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
      zIndex: 9999,
    }}>
      <div style={{
        fontSize: '11px',
        fontWeight: 600,
        color: 'var(--text-secondary)',
        marginBottom: '6px',
        letterSpacing: '0.02em',
      }}>
        {headerText}
      </div>
      <div style={{
        borderTop: '1px solid var(--border)',
        paddingTop: '4px',
      }}>
        {allVotes.map(({ vote, isPriority }) => (
          <VoteRow key={vote.source_name} vote={vote} isPriority={isPriority} />
        ))}
      </div>
    </div>,
    document.body
  )
}
