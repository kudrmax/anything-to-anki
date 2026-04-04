import type { StoredCandidate } from '@/api/types'
import { cn } from '@/lib/utils'

interface TextAnnotatorProps {
  text: string
  candidates: StoredCandidate[]
  hoveredCandidateId: number | null
  onWordClick: (candidateId: number) => void
  onWordHover: (candidateId: number | null) => void
}

const CEFR_HIGHLIGHT: Record<string, string> = {
  B2: 'bg-amber-400/15 text-amber-300 border-b border-amber-500/50',
  C1: 'bg-orange-400/15 text-orange-300 border-b border-orange-500/50',
  C2: 'bg-rose-400/15 text-rose-300 border-b border-rose-500/50',
}

const CEFR_HIGHLIGHT_HOVERED: Record<string, string> = {
  B2: 'bg-amber-400/35 text-amber-200 border-b-2 border-amber-400',
  C1: 'bg-orange-400/35 text-orange-200 border-b-2 border-orange-400',
  C2: 'bg-rose-400/35 text-rose-200 border-b-2 border-rose-400',
}

type TextSegment =
  | { type: 'text'; content: string }
  | { type: 'mark'; content: string; candidateId: number; cefrLevel: string }

function buildSegments(text: string, candidates: StoredCandidate[]): TextSegment[] {
  // Build list of (start, end, candidate) matches in the text
  type Match = { start: number; end: number; candidate: StoredCandidate }
  const matches: Match[] = []

  for (const candidate of candidates) {
    // Try to find context_fragment first, then lemma
    const targets = [candidate.context_fragment, candidate.lemma].filter(Boolean)
    let found = false
    for (const target of targets) {
      const idx = text.toLowerCase().indexOf(target.toLowerCase())
      if (idx !== -1) {
        matches.push({ start: idx, end: idx + target.length, candidate })
        found = true
        break
      }
    }
    if (!found) {
      // Word-boundary search for lemma in text
      const re = new RegExp(`\\b${candidate.lemma}\\b`, 'i')
      const m = re.exec(text)
      if (m) {
        matches.push({ start: m.index, end: m.index + m[0].length, candidate })
      }
    }
  }

  // Sort by start position, remove overlaps
  matches.sort((a, b) => a.start - b.start)
  const nonOverlapping: Match[] = []
  let cursor = 0
  for (const m of matches) {
    if (m.start >= cursor) {
      nonOverlapping.push(m)
      cursor = m.end
    }
  }

  // Build segments
  const segments: TextSegment[] = []
  let pos = 0
  for (const m of nonOverlapping) {
    if (m.start > pos) {
      segments.push({ type: 'text', content: text.slice(pos, m.start) })
    }
    segments.push({
      type: 'mark',
      content: text.slice(m.start, m.end),
      candidateId: m.candidate.id,
      cefrLevel: m.candidate.cefr_level,
    })
    pos = m.end
  }
  if (pos < text.length) {
    segments.push({ type: 'text', content: text.slice(pos) })
  }
  return segments
}

export function TextAnnotator({
  text,
  candidates,
  hoveredCandidateId,
  onWordClick,
  onWordHover,
}: TextAnnotatorProps) {
  const segments = buildSegments(text, candidates)

  return (
    <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap font-mono">
      {segments.map((seg, i) => {
        if (seg.type === 'text') {
          return <span key={i}>{seg.content}</span>
        }
        const isHovered = hoveredCandidateId === seg.candidateId
        const baseCls = CEFR_HIGHLIGHT[seg.cefrLevel] ?? 'bg-slate-700/40 text-slate-300 border-b border-slate-500'
        const hoveredCls = CEFR_HIGHLIGHT_HOVERED[seg.cefrLevel] ?? 'bg-slate-600/60 text-slate-100 border-b-2 border-slate-400'
        return (
          <mark
            key={i}
            data-candidate-id={seg.candidateId}
            className={cn(
              'cursor-pointer rounded-sm px-0.5 transition-colors bg-transparent',
              isHovered ? hoveredCls : baseCls,
            )}
            onClick={() => onWordClick(seg.candidateId)}
            onMouseEnter={() => onWordHover(seg.candidateId)}
            onMouseLeave={() => onWordHover(null)}
          >
            {seg.content}
          </mark>
        )
      })}
    </div>
  )
}
