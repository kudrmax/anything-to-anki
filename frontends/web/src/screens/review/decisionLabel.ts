import type { DecisionButton } from '@/api/types'

/** Подпись кнопки решения: на самой кнопке и в тосте её нажатия. */
export const DECISION_LABEL: Record<DecisionButton, string> = {
  learn: 'Learn',
  cloze: 'Cloze',
  known: 'Know',
  skip: 'Skip',
}

const DONE: Record<DecisionButton, (word: string) => string> = {
  learn: word => `Marked ${word} to learn`,
  cloze: word => `Marked ${word} as cloze`,
  known: word => `Marked ${word} as known`,
  skip: word => `Skipped ${word}`,
}
const UNMARKED = (word: string) => `Unmarked ${word}`
const THE_CARD = 'the card'

/** Тост нажатия: что стало с карточкой. `null` — нажатие сняло отметку. */
export function decisionDone(button: DecisionButton | null, lemma: string | undefined): string {
  const word = lemma ?? THE_CARD
  return button === null ? UNMARKED(word) : DONE[button](word)
}
