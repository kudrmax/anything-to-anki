import type { CardPhrase } from '@/api/types'

/** Кусок фразы карточки: слово (с его номером) или то, что между словами. */
export interface PhrasePart {
  text: string
  word: number | null
  target: boolean
  hidden: boolean
}

/** Режет текст фразы по словам, которые прислал backend: target и скрытые слова — по номерам. */
export function phraseParts(phrase: CardPhrase, hidden: ReadonlySet<number> = new Set()): PhrasePart[] {
  const target = new Set(phrase.target)
  const parts: PhrasePart[] = []
  let position = 0
  phrase.words.forEach(([start, end], word) => {
    if (start > position) parts.push({ text: phrase.text.slice(position, start), word: null, target: false, hidden: false })
    parts.push({ text: phrase.text.slice(start, end), word, target: target.has(word), hidden: hidden.has(word) })
    position = end
  })
  if (position < phrase.text.length) parts.push({ text: phrase.text.slice(position), word: null, target: false, hidden: false })
  return parts
}

/** Слова фразы по порядку, как их считает backend. */
export const phraseWordTexts = (phrase: CardPhrase): string[] =>
  phrase.words.map(([start, end]) => phrase.text.slice(start, end))

/** Изучаемое слово так, как оно написано во фразе: «gave up» для «gave it up». */
export const targetText = (phrase: CardPhrase): string =>
  phrase.target.map(i => phrase.text.slice(...phrase.words[i])).join(' ')
