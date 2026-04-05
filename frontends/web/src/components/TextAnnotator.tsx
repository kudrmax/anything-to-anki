import { useCallback, useRef, useState } from 'react'
import type { StoredCandidate } from '@/api/types'
import { cn } from '@/lib/utils'
import { SelectionPopover } from '@/components/SelectionPopover'

interface TextAnnotatorProps {
  text: string
  candidates: StoredCandidate[]
  hoveredCandidateId: number | null
  ratedIds: Set<number>
  onWordClick: (candidateId: number) => void
  onWordHover: (candidateId: number | null) => void
  onManualAdd?: (surfaceForm: string, contextFragment: string) => Promise<void>
}

const CEFR_HIGHLIGHT: Record<string, string> = {
  B2: 'bg-amber-400/15 text-amber-300 border-b border-amber-500/50',
  C1: 'bg-orange-400/15 text-orange-300 border-b border-orange-500/50',
  C2: 'bg-rose-400/15 text-rose-300 border-b border-rose-500/50',
}

const CEFR_HIGHLIGHT_HOVERED: Record<string, string> = {
  B2: 'bg-amber-400/40 text-amber-100 border-b-2 border-amber-400',
  C1: 'bg-orange-400/40 text-orange-100 border-b-2 border-orange-400',
  C2: 'bg-rose-400/40 text-rose-100 border-b-2 border-rose-400',
}

type TextSegment =
  | { type: 'text'; content: string; start: number }
  | { type: 'mark'; content: string; start: number; candidateId: number; cefrLevel: string | null }

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function buildSegments(text: string, candidates: StoredCandidate[]): TextSegment[] {
  type Match = { start: number; end: number; candidate: StoredCandidate; exact: boolean }
  const matches: Match[] = []

  for (const candidate of candidates) {
    if (candidate.surface_form) {
      const idx = text.toLowerCase().indexOf(candidate.surface_form.toLowerCase())
      if (idx !== -1) {
        matches.push({ start: idx, end: idx + candidate.surface_form.length, candidate, exact: true })
      }
    } else {
      const re = new RegExp(`\\b${escapeRegex(candidate.lemma)}\\w*`, 'i')
      const m = re.exec(text)
      if (m) {
        matches.push({ start: m.index, end: m.index + m[0].length, candidate, exact: false })
      }
    }
  }

  matches.sort((a, b) => {
    if (a.exact !== b.exact) return a.exact ? -1 : 1
    return a.start - b.start
  })

  const taken: Array<{ start: number; end: number }> = []
  const nonOverlapping: Match[] = []
  for (const m of matches) {
    const overlaps = taken.some(t => m.start < t.end && m.end > t.start)
    if (!overlaps) {
      nonOverlapping.push(m)
      taken.push({ start: m.start, end: m.end })
    }
  }

  nonOverlapping.sort((a, b) => a.start - b.start)

  const segments: TextSegment[] = []
  let pos = 0
  for (const m of nonOverlapping) {
    if (m.start > pos) {
      segments.push({ type: 'text', content: text.slice(pos, m.start), start: pos })
    }
    segments.push({
      type: 'mark',
      content: text.slice(m.start, m.end),
      start: m.start,
      candidateId: m.candidate.id,
      cefrLevel: m.candidate.cefr_level ?? null,
    })
    pos = m.end
  }
  if (pos < text.length) {
    segments.push({ type: 'text', content: text.slice(pos), start: pos })
  }
  return segments
}

export function TextAnnotator({
  text,
  candidates,
  hoveredCandidateId,
  ratedIds,
  onWordClick,
  onWordHover,
  onManualAdd,
}: TextAnnotatorProps) {
  const segments = buildSegments(text, candidates)
  const containerRef = useRef<HTMLDivElement>(null)
  const [popover, setPopover] = useState<{ phrase: string; position: { x: number; y: number } } | null>(null)

  const handleMouseUp = useCallback(() => {
    if (!onManualAdd) return
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || !sel.rangeCount) return
    const phrase = sel.toString().trim()
    if (!phrase) return

    const range = sel.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    setPopover({ phrase, position: { x: rect.left + rect.width / 2, y: rect.top } })
  }, [onManualAdd])

  const handlePopoverAdd = useCallback(async (targetTokens: string[], contextFragment: string) => {
    const surfaceForm = targetTokens.join(' ')
    await onManualAdd?.(surfaceForm, contextFragment)
    setPopover(null)
    window.getSelection()?.removeAllRanges()
  }, [onManualAdd])

  const handlePopoverClose = useCallback(() => {
    setPopover(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  // Find fragment bounds in the full text for the hovered candidate
  let fragmentStart = -1
  let fragmentEnd = -1
  if (hoveredCandidateId !== null) {
    const hovered = candidates.find(c => c.id === hoveredCandidateId)
    if (hovered?.context_fragment) {
      const idx = text.toLowerCase().indexOf(hovered.context_fragment.toLowerCase())
      if (idx !== -1) {
        fragmentStart = idx
        fragmentEnd = idx + hovered.context_fragment.length
      }
    }
  }

  const isDimming = hoveredCandidateId !== null

  return (
    <>
    <div
      ref={containerRef}
      onMouseUp={handleMouseUp}
      className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap font-mono"
    >
      {segments.map((seg, i) => {
        const segEnd = seg.start + seg.content.length
        const inFragment = fragmentStart !== -1 && seg.start < fragmentEnd && segEnd > fragmentStart

        if (seg.type === 'text') {
          if (!isDimming || fragmentStart === -1) {
            return <span key={i}>{seg.content}</span>
          }
          const overlapStart = Math.max(seg.start, fragmentStart)
          const overlapEnd = Math.min(segEnd, fragmentEnd)
          if (overlapStart >= overlapEnd) {
            return (
              <span key={i} style={{ opacity: 0.15, transition: 'opacity 150ms ease' }}>
                {seg.content}
              </span>
            )
          }
          const before = seg.content.slice(0, overlapStart - seg.start)
          const inside = seg.content.slice(overlapStart - seg.start, overlapEnd - seg.start)
          const after = seg.content.slice(overlapEnd - seg.start)
          return (
            <span key={i}>
              {before && <span style={{ opacity: 0.15, transition: 'opacity 150ms ease' }}>{before}</span>}
              <span style={{ opacity: 1, transition: 'opacity 150ms ease' }}>{inside}</span>
              {after && <span style={{ opacity: 0.15, transition: 'opacity 150ms ease' }}>{after}</span>}
            </span>
          )
        }

        const isActive = hoveredCandidateId === seg.candidateId
        const isRated = ratedIds.has(seg.candidateId)
        const baseCls = (seg.cefrLevel && CEFR_HIGHLIGHT[seg.cefrLevel]) ?? 'bg-slate-400/10 text-slate-400 border-b border-slate-500/40'
        const hoveredCls = (seg.cefrLevel && CEFR_HIGHLIGHT_HOVERED[seg.cefrLevel]) ?? 'bg-slate-400/25 text-slate-200 border-b-2 border-slate-400'

        let markCls: string
        let opacity: number

        if (isActive) {
          markCls = cn('cursor-pointer rounded-sm px-0.5', hoveredCls)
          opacity = 1
        } else if (isRated) {
          // Rated but not active: blend into regular text, no visual distinction
          markCls = 'cursor-pointer'
          opacity = isDimming && !inFragment ? 0.15 : 1
        } else {
          markCls = cn('cursor-pointer rounded-sm px-0.5', baseCls)
          opacity = isDimming && !inFragment ? 0.15 : 1
        }

        return (
          <mark
            key={i}
            data-candidate-id={seg.candidateId}
            className={markCls}
            style={{ opacity, transition: 'opacity 150ms ease', ...(isRated && !isActive && { color: 'inherit', background: 'transparent' }) }}
            onClick={() => onWordClick(seg.candidateId)}
            onMouseEnter={() => onWordHover(seg.candidateId)}
            onMouseLeave={() => onWordHover(null)}
          >
            {seg.content}
          </mark>
        )
      })}
    </div>
    {popover && (
      <SelectionPopover
        phrase={popover.phrase}
        position={popover.position}
        onAdd={handlePopoverAdd}
        onClose={handlePopoverClose}
      />
    )}
    </>
  )
}
