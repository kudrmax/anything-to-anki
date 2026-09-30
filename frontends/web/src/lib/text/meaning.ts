import type { CandidateMeaning } from '@/api/types'

export const FREQ_BAND_LABEL: Record<string, string> = {
  ULTRA_COMMON: 'Ultra Common',
  COMMON: 'Common',
  MID: 'Mid',
  LOW: 'Low',
  RARE: 'Rare',
}

export interface TextPart {
  text: string
  bold: boolean
  target: boolean
}

export function primaryUsageGroup(dist: Record<string, number> | null): string | null {
  if (!dist) return null
  const keys = Object.keys(dist)
  if (keys.length === 0) return null
  const first = keys[0]
  return first === 'neutral' ? null : first
}

export function stripMarkdown(text: string): string {
  return text
    .replace(/\*{2}(.+?)\*{2}/gs, '$1')
    .replace(/_{2}(.+?)_{2}/gs, '$1')
    .replace(/\*(.+?)\*/gs, '$1')
    .replace(/_(.+?)_/gs, '$1')
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function buildHighlightPattern(lemma: string, surfaceForm: string | null): RegExp {
  const patterns: string[] = []
  if (surfaceForm) patterns.push(escapeRegex(surfaceForm))
  const words = lemma.split(' ')
  if (words.length === 1) {
    patterns.push(`\\b${escapeRegex(lemma)}\\w*`)
  } else {
    const rest = words.slice(1).map(escapeRegex).join('\\s+')
    patterns.push(`\\b${escapeRegex(words[0])}\\w*\\s+${rest}\\b`)
  }
  return new RegExp(`(${patterns.join('|')})`, 'gi')
}

/** Фрагмент с выделенным первым вхождением изучаемого слова. */
export function highlightParts(fragment: string, lemma: string, surfaceForm: string | null): TextPart[] {
  const clean = stripMarkdown(fragment)
  const pattern = buildHighlightPattern(lemma, surfaceForm)
  const match = pattern.exec(clean)
  if (!match) return [{ text: clean, bold: false, target: false }]
  const parts: TextPart[] = [
    { text: clean.slice(0, match.index), bold: false, target: false },
    { text: match[0], bold: false, target: true },
    { text: clean.slice(match.index + match[0].length), bold: false, target: false },
  ]
  return parts.filter(part => part.text.length > 0)
}

/** Текст значения: **жирные** участки и все вхождения изучаемого слова. */
export function meaningParts(text: string, lemma: string, surfaceForm: string | null): TextPart[] {
  const pattern = buildHighlightPattern(lemma, surfaceForm)
  const parts: TextPart[] = []
  const boldPattern = /\*{2}(.+?)\*{2}/g
  let idx = 0
  let boldMatch: RegExpExecArray | null

  const addTextWithHighlight = (segment: string, bold: boolean) => {
    const p = new RegExp(pattern.source, pattern.flags)
    let last = 0
    let m: RegExpExecArray | null
    while ((m = p.exec(segment)) !== null) {
      if (m.index > last) parts.push({ text: segment.slice(last, m.index), bold, target: false })
      parts.push({ text: m[0], bold: false, target: true })
      last = m.index + m[0].length
    }
    if (last < segment.length) parts.push({ text: segment.slice(last), bold, target: false })
  }

  while ((boldMatch = boldPattern.exec(text)) !== null) {
    if (boldMatch.index > idx) addTextWithHighlight(text.slice(idx, boldMatch.index), false)
    addTextWithHighlight(boldMatch[1], true)
    idx = boldMatch.index + boldMatch[0].length
  }
  if (idx < text.length) addTextWithHighlight(text.slice(idx), false)
  return parts
}

/** Непустые строки многострочного текста. */
export function nonEmptyLines(text: string): string[] {
  return text.split(/\n+/).filter(line => line.trim().length > 0)
}

export const isDivider = (line: string): boolean => /^---+$/.test(line.trim())

export function parseExamples(examples: string | null | undefined): string[] {
  if (!examples) return []
  return examples
    .split('\n')
    .map(line => line.replace(/\*{2}(.+?)\*{2}/g, '$1').trim())
    .filter(line => line.length > 0)
}

/** Медиа отдаётся относительным путём /media/{source}/{имя файла}. */
export function mediaUrl(sourceId: number, path: string | null | undefined): string | null {
  return path ? `/media/${sourceId}/${path.split('/').pop()}` : null
}

/** Что предложить во фразе без текста значения: сгенерировать, повторить после ошибки или ничего. */
export function meaningAction(meaning: CandidateMeaning | null): 'generate' | 'retry' | null {
  if (meaning?.meaning || meaning?.status === 'running') return null
  return meaning?.status === 'failed' ? 'retry' : 'generate'
}
