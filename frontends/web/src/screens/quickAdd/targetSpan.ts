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
