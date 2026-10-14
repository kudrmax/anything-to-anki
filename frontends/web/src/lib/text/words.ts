// Слово: буквы и цифры, с апострофами и дефисами внутри («don't», «well-known») — как у backend.
const WORD = /(?:[\p{L}\p{N}]|['’-])+/gu
const EDGE = /^['’-]+|['’-]+$/g

interface WordSpan {
  start: number
  end: number
}

const wordSpans = (text: string): WordSpan[] =>
  [...text.matchAll(WORD)].flatMap(match => {
    const word = match[0]
    const lead = word.length - word.replace(/^['’-]+/, '').length
    const trimmed = word.replace(EDGE, '')
    const start = (match.index ?? 0) + lead
    return trimmed ? [{ start, end: start + trimmed.length }] : []
  })

/** Слова ещё не разобранного текста в том виде, в каком их показывает WordPicker. */
export const phraseWords = (text: string): string[] =>
  wordSpans(text).map(({ start, end }) => text.slice(start, end))

/** Номера слов текста, которых касаются выделенные куски. */
export const wordsIn = (text: string, spans: readonly WordSpan[]): number[] =>
  wordSpans(text).flatMap((word, i) =>
    spans.some(span => span.start < word.end && word.start < span.end) ? [i] : [])

/** Номера выбранных слов по порядку текста. */
export const pickedIndices = (selected: ReadonlySet<number>): number[] =>
  [...selected].sort((a, b) => a - b)

/** Выбранные слова по порядку текста, через пробел. */
export const pickedWords = (text: string, selected: ReadonlySet<number>): string =>
  phraseWords(text).filter((_, i) => selected.has(i)).join(' ')

/** Переключает индекс в наборе выбранных слов. */
export const toggled = (selected: ReadonlySet<number>, index: number): Set<number> => {
  const next = new Set(selected)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  return next
}
