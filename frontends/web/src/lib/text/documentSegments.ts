import type { DocumentPosition } from '@/api/types'

/** Кусок строки документа: обычный текст или target; позиции — в code points, как у backend. */
export interface LineSegment {
  /** Где кусок начинается в строке. */
  start: number
  text: string
  markId: number | null
  inFragment: boolean
}

export interface LineMark {
  candidateId: number
  position: DocumentPosition
}

/** Отрезок строки [from, to), который позиция занимает в этой строке, или null. */
export function spanInLine(position: DocumentPosition, block: number, line: number, length: number): [number, number] | null {
  if (position.block !== block || line < position.start_line || line > position.end_line) return null
  const from = line === position.start_line ? position.start_char : 0
  const to = line === position.end_line ? position.end_char : length
  return from < to ? [from, to] : null
}

/** Строка, разрезанная по target'ам и по краям фразы в фокусе. */
export function lineSegments(
  text: string,
  block: number,
  line: number,
  marks: readonly LineMark[],
  fragment: DocumentPosition | null,
): LineSegment[] {
  const chars = Array.from(text)
  const markSpans = marks
    .map(mark => ({ id: mark.candidateId, span: spanInLine(mark.position, block, line, chars.length) }))
    .filter((mark): mark is { id: number; span: [number, number] } => mark.span !== null)
  const fragmentSpan = fragment ? spanInLine(fragment, block, line, chars.length) : null

  const cuts = new Set([0, chars.length])
  for (const mark of markSpans) mark.span.forEach(cut => cuts.add(cut))
  if (fragmentSpan) fragmentSpan.forEach(cut => cuts.add(cut))
  const points = [...cuts].sort((a, b) => a - b)

  const segments: LineSegment[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const [from, to] = [points[i], points[i + 1]]
    const mark = markSpans.find(m => m.span[0] <= from && to <= m.span[1])
    segments.push({
      start: from,
      text: chars.slice(from, to).join(''),
      markId: mark?.id ?? null,
      inFragment: fragmentSpan !== null && fragmentSpan[0] <= from && to <= fragmentSpan[1],
    })
  }
  return segments
}

/** Сколько code points в начале строки занимают первые `utf16Offset` единиц UTF-16. */
export function codePointOffset(text: string, utf16Offset: number): number {
  return Array.from(text.slice(0, utf16Offset)).length
}
