/** Слова фразы в том виде, в каком их показывает WordPicker. */
export const phraseWords = (phrase: string): string[] => phrase.split(/\s+/).filter(Boolean)

/** Выбранные слова по порядку фразы, через пробел. */
export const pickedWords = (phrase: string, selected: ReadonlySet<number>): string =>
  phraseWords(phrase).filter((_, i) => selected.has(i)).join(' ')

/** Переключает индекс в наборе выбранных слов. */
export const toggled = (selected: ReadonlySet<number>, index: number): Set<number> => {
  const next = new Set(selected)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  return next
}
