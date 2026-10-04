export interface Span {
  start: number
  end: number
}

const WORD_CHAR = /[\p{L}\p{N}'’-]/u

const isWordChar = (char: string | undefined) => char !== undefined && WORD_CHAR.test(char)

/** Выделение мышью почти никогда не попадает ровно в границы слов: дотягиваем его до целых слов. */
export function snapToWords(text: string, start: number, end: number): Span | null {
  let from = Math.max(0, Math.min(start, end))
  let to = Math.min(text.length, Math.max(start, end))
  while (from < to && !isWordChar(text[from])) from++
  while (to > from && !isWordChar(text[to - 1])) to--
  if (from === to) return null
  while (from > 0 && isWordChar(text[from - 1])) from--
  while (to < text.length && isWordChar(text[to])) to++
  return { start: from, end: to }
}

/** Текст из браузера приходит с переносами строк и двойными пробелами вёрстки. */
export function normalizePhrase(raw: string): string {
  return raw.replace(/\s+/g, ' ').trim()
}

const overlaps = (a: Span, b: Span) => a.start < b.end && b.start < a.end

/**
 * Target может состоять из кусков фразы: разорванный фразовый глагол «give it up» — это «give» и «up».
 * Без добавления выделение заменяет target. С добавлением новый кусок встаёт к остальным,
 * а повторное выделение уже выбранного снимает его.
 */
export function pickSpan(spans: readonly Span[], span: Span, additive: boolean): Span[] {
  if (!additive) return [span]
  const rest = spans.filter(existing => !overlaps(existing, span))
  if (rest.length < spans.length) return rest
  return [...rest, span].sort((a, b) => a.start - b.start)
}

export function targetText(text: string, spans: readonly Span[]): string {
  return spans.map(span => text.slice(span.start, span.end)).join(' ')
}

export interface Segment {
  text: string
  picked: boolean
}

export function segments(text: string, spans: readonly Span[]): Segment[] {
  const result: Segment[] = []
  let cursor = 0
  for (const span of spans) {
    if (span.start > cursor) result.push({ text: text.slice(cursor, span.start), picked: false })
    result.push({ text: text.slice(span.start, span.end), picked: true })
    cursor = span.end
  }
  if (cursor < text.length) result.push({ text: text.slice(cursor), picked: false })
  return result
}
