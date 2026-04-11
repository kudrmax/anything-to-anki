import { useCallback, useRef } from 'react'
import type { StoredCandidate } from '@/api/types'
import { FONT_BODY } from '@/lib/design-tokens'

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
}

const MARK_STYLE_HOVERED: React.CSSProperties = {
  background: 'var(--hl-bg-hover)',
  color: 'var(--hl-text-hover)',
}

function cefrMarkStyle(level: string): React.CSSProperties {
  const k = level.toLowerCase()
  return {
    background: `var(--hl-${k}-bg)`,
    color: `var(--hl-${k}-text)`,
  }
}

function cefrMarkStyleHovered(level: string): React.CSSProperties {
  const k = level.toLowerCase()
  return {
    background: `var(--hl-${k}-bg)`,
    color: `var(--hl-${k}-text)`,
    filter: 'brightness(1.3)',
  }
}

type TextSegment =
  | { type: 'text'; content: string; start: number }
  | { type: 'mark'; content: string; start: number; candidateId: number; cefrLevel: string | null }

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Build a regex from a phrase where any whitespace matches any whitespace (space, newline, etc.) */
function flexWsPattern(phrase: string): string {
  return phrase.trim().split(/\s+/).map(escapeRegex).join('\\s+')
}

function buildSegments(text: string, candidates: StoredCandidate[]): TextSegment[] {
  type Match = { start: number; end: number; candidate: StoredCandidate; exact: boolean }
  const matches: Match[] = []

  for (const candidate of candidates) {
    // Build the target regex
    let targetRe: RegExp
    let exact: boolean
    if (candidate.surface_form) {
      targetRe = new RegExp(flexWsPattern(candidate.surface_form), 'i')
      exact = true
    } else {
      const words = candidate.lemma.split(/\s+/)
      if (words.length === 1) {
        targetRe = new RegExp(`\\b${escapeRegex(candidate.lemma)}\\w*`, 'i')
      } else {
        const first = escapeRegex(words[0])
        const rest = words.slice(1).map(escapeRegex).join('\\s+')
        targetRe = new RegExp(`\\b${first}\\w*\\s+${rest}`, 'i')
      }
      exact = false
    }

    // Search within context_fragment first, then fall back to full text
    let m: { index: number; length: number } | null = null
    if (candidate.context_fragment) {
      const fragRe = new RegExp(flexWsPattern(candidate.context_fragment), 'i')
      const fragMatch = fragRe.exec(text)
      if (fragMatch) {
        const fragSlice = text.slice(fragMatch.index, fragMatch.index + fragMatch[0].length)
        const inner = targetRe.exec(fragSlice)
        if (inner) {
          m = { index: fragMatch.index + inner.index, length: inner[0].length }
        }
      }
    }
    if (!m) {
      const fullMatch = targetRe.exec(text)
      if (fullMatch) {
        m = { index: fullMatch.index, length: fullMatch[0].length }
      }
    }

    if (m) {
      matches.push({ start: m.index, end: m.index + m.length, candidate, exact })
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
      cefrLevel: m.candidate.is_phrasal_verb ? 'phrasal' : (m.candidate.cefr_level ?? null),
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
    if (hovered?.context_fragment && !hovered.has_custom_context_fragment) {
      const fragRe = new RegExp(flexWsPattern(hovered.context_fragment), 'i')
      const fragMatch = fragRe.exec(text)
      if (fragMatch) {
        fragmentStart = fragMatch.index
        fragmentEnd = fragMatch.index + fragMatch[0].length
      }
    }
  }

  const isDimming = !disableHoverDimming && effectiveHoveredId !== null

  return (
    <div
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      className="leading-normal whitespace-pre-wrap"
      style={{ color: 'var(--tm)', fontSize: FONT_BODY }}
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
          markStyle = { ...cefrHover, cursor: 'pointer' }
          opacity = 1
        } else if (isRated) {
          markStyle = { cursor: 'pointer', color: 'inherit', background: 'transparent' }
          opacity = isDimming && !inFragment ? 0.15 : 1
        } else {
          markStyle = { ...cefrBase, cursor: 'pointer' }
          opacity = isDimming && !inFragment ? 0.15 : 1
        }

        const isRatedNoGlass = isRated && !isActive

        return (
          <mark
            key={i}
            data-candidate-id={seg.candidateId}
            className={isRatedNoGlass ? '' : 'glass-word'}
            style={{ ...markStyle, opacity, transition: 'opacity 150ms ease' }}
            onClick={() => onWordClick(seg.candidateId)}
            onMouseEnter={() => { if (!isDraggingRef.current) onWordHover(seg.candidateId) }}
            onMouseLeave={() => { if (!isDraggingRef.current) onWordHover(null) }}
          >
            {seg.content.replace(/\s+/g, ' ')}
          </mark>
        )
      })}
    </div>
  )
}
