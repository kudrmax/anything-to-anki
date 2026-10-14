// Слово: буквы и цифры, с апострофами и дефисами внутри («don't», «well-known») — как у backend.
const WORD = /(?:[\p{L}\p{N}]|['’-])+/gu
const EDGE = /^['’-]+|['’-]+$/g

/** Слова ещё не разобранного текста в том виде, в каком их показывает WordPicker. */
export const phraseWords = (text: string): string[] =>
  [...text.matchAll(WORD)].map(([word]) => word.replace(EDGE, '')).filter(Boolean)

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
