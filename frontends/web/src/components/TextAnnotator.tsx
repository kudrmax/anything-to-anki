import { useCallback, useRef } from 'react'
import type { StoredCandidate } from '@/api/types'

interface TextAnnotatorProps {
  text: string
  candidates: StoredCandidate[]
  hoveredCandidateId: number | null
  ratedIds: Set<number>
  onWordClick: (candidateId: number) => void
  onWordHover: (candidateId: number | null) => void
  onTextSelected?: (phrase: string, position: { x: number; y: number; yBottom: number }) => void
  editingFragmentFor?: number | null
  disableHoverDimming?: boolean
}

const MARK_STYLE: React.CSSProperties = {
  background: 'var(--hl-bg)',
  color: 'var(--hl-text)',
  borderBottom: '1px solid var(--hl-border)',
}

const MARK_STYLE_HOVERED: React.CSSProperties = {
  background: 'var(--hl-bg-hover)',
  color: 'var(--hl-text-hover)',
  borderBottom: '2px solid var(--hl-border-hover)',
}

function cefrMarkStyle(level: string): React.CSSProperties {
  const k = level as string
  return {
    background: `var(--hl-${k.toLowerCase()}-bg)`,
    color: `var(--hl-${k.toLowerCase()}-text)`,
    borderBottom: `1px solid var(--hl-${k.toLowerCase()}-border)`,
  }
}

function cefrMarkStyleHovered(level: string): React.CSSProperties {
  const k = level as string
  return {
    background: `var(--hl-${k.toLowerCase()}-bg)`,
    color: `var(--hl-${k.toLowerCase()}-text)`,
    borderBottom: `2px solid var(--hl-${k.toLowerCase()}-border)`,
    filter: 'brightness(1.3)',
  }
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
  onTextSelected,
  editingFragmentFor,
  disableHoverDimming,
}: TextAnnotatorProps) {
  const segments = buildSegments(text, candidates)
  const containerRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)

  // In edit mode, always highlight the fragment being edited regardless of hover
  const effectiveHoveredId = editingFragmentFor != null ? editingFragmentFor : hoveredCandidateId

  const handleMouseDown = useCallback(() => {
    isDraggingRef.current = true
  }, [])

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || !sel.rangeCount) return
    const phrase = sel.toString().trim()
    if (!phrase) return

    const range = sel.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    onTextSelected?.(phrase, {
      x: rect.left + rect.width / 2,
      y: rect.top,
      yBottom: rect.bottom,
    })
  }, [onTextSelected])

  // Find fragment bounds in the full text for the effective hovered candidate
  let fragmentStart = -1
  let fragmentEnd = -1
  if (effectiveHoveredId !== null) {
    const hovered = candidates.find(c => c.id === effectiveHoveredId)
    if (hovered?.context_fragment) {
      const idx = text.toLowerCase().indexOf(hovered.context_fragment.toLowerCase())
      if (idx !== -1) {
        fragmentStart = idx
        fragmentEnd = idx + hovered.context_fragment.length
      }
    }
  }

  const isDimming = !disableHoverDimming && effectiveHoveredId !== null

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      className="text-lg leading-relaxed whitespace-pre-wrap"
      style={{ color: 'var(--tm)' }}
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

        const isActive = effectiveHoveredId === seg.candidateId
        const isRated = ratedIds.has(seg.candidateId)

        let markStyle: React.CSSProperties
        let opacity: number

        const cefrBase = seg.cefrLevel ? cefrMarkStyle(seg.cefrLevel) : MARK_STYLE
        const cefrHover = seg.cefrLevel ? cefrMarkStyleHovered(seg.cefrLevel) : MARK_STYLE_HOVERED

        if (isActive) {
          markStyle = { ...cefrHover, cursor: 'pointer', borderRadius: '2px', padding: '0 2px' }
          opacity = 1
        } else if (isRated) {
          markStyle = { cursor: 'pointer', color: 'inherit', background: 'transparent' }
          opacity = isDimming && !inFragment ? 0.15 : 1
        } else {
          markStyle = { ...cefrBase, cursor: 'pointer', borderRadius: '2px', padding: '0 2px' }
          opacity = isDimming && !inFragment ? 0.15 : 1
        }

        return (
          <mark
            key={i}
            data-candidate-id={seg.candidateId}
            style={{ ...markStyle, opacity, transition: 'opacity 150ms ease' }}
            onClick={() => onWordClick(seg.candidateId)}
            onMouseEnter={() => { if (!isDraggingRef.current) onWordHover(seg.candidateId) }}
            onMouseLeave={() => { if (!isDraggingRef.current) onWordHover(null) }}
          >
            {seg.content}
          </mark>
        )
      })}
    </div>
  )
}
