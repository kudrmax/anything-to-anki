import type { StoredCandidate } from '@/api/types'

export type TextSegment =
  | { type: 'text'; content: string; start: number }
  | { type: 'mark'; content: string; start: number; candidateId: number; cefrLevel: string | null }

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Build a regex from a phrase where any whitespace matches any whitespace (space, newline, etc.) */
export function flexWsPattern(phrase: string): string {
  return phrase.trim().split(/\s+/).map(escapeRegex).join('\\s+')
}

export function buildSegments(text: string, candidates: StoredCandidate[]): TextSegment[] {
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

    // Fallback regex for phrasal verbs: allows 0-3 words between parts
    let fallbackRe: RegExp | null = null
    if (candidate.is_phrasal_verb) {
      const lemmaWords = candidate.lemma.split(/\s+/)
      if (lemmaWords.length >= 2) {
        const first = escapeRegex(lemmaWords[0])
        const rest = lemmaWords.slice(1).map(escapeRegex).join('\\s+')
        fallbackRe = new RegExp(`\\b${first}\\w*(?:\\s+\\S+){0,3}?\\s+${rest}\\b`, 'i')
      }
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
    // Phrasal verb fallback: try flexible regex allowing words between parts
    if (!m && fallbackRe) {
      if (candidate.context_fragment) {
        const fragRe = new RegExp(flexWsPattern(candidate.context_fragment), 'i')
        const fragMatch = fragRe.exec(text)
        if (fragMatch) {
          const fragSlice = text.slice(fragMatch.index, fragMatch.index + fragMatch[0].length)
          const inner = fallbackRe.exec(fragSlice)
          if (inner) {
            m = { index: fragMatch.index + inner.index, length: inner[0].length }
          }
        }
      }
      if (!m) {
        const fullMatch = fallbackRe.exec(text)
        if (fullMatch) {
          m = { index: fullMatch.index, length: fullMatch[0].length }
        }
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

/** Границы фрагмента кандидата в полном тексте; null, если фрагмент задан вручную или не найден. */
export function fragmentBounds(text: string, candidate: StoredCandidate | undefined): { start: number; end: number } | null {
  if (!candidate?.context_fragment || candidate.has_custom_context_fragment) return null
  const fragRe = new RegExp(flexWsPattern(candidate.context_fragment), 'i')
  const fragMatch = fragRe.exec(text)
  if (!fragMatch) return null
  return { start: fragMatch.index, end: fragMatch.index + fragMatch[0].length }
}
