import type { TextPart } from '@/lib/text/meaning'

export interface ClozePart {
  text: string
  target: boolean
  hidden: boolean
}

const SPACE_OR_WORD = /\s+|\S+/g

/**
 * Делит подсвеченную фразу на куски, отмечая слова, которые backend сохранил скрытыми.
 * Слова считаются так же, как их нумерует backend: по пробелам.
 */
export function clozeParts(parts: TextPart[], hiddenIndices: number[]): ClozePart[] {
  const hidden = new Set(hiddenIndices)
  const result: ClozePart[] = []
  let word = -1
  let afterSpace = true
  const push = (piece: ClozePart) => {
    const last = result[result.length - 1]
    if (last && last.target === piece.target && last.hidden === piece.hidden) last.text += piece.text
    else result.push(piece)
  }
  for (const part of parts) {
    for (const [chunk] of part.text.matchAll(SPACE_OR_WORD)) {
      const isSpace = /^\s/.test(chunk)
      if (!isSpace && afterSpace) word += 1
      afterSpace = isSpace
      push({ text: chunk, target: part.target, hidden: !isSpace && hidden.has(word) })
    }
  }
  return result
}
