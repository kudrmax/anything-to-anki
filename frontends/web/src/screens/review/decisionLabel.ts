import type { DecisionButton } from '@/api/types'

/** Подпись кнопки решения: на самой кнопке и в тосте её нажатия. */
export const DECISION_LABEL: Record<DecisionButton, string> = {
  learn: 'Learn',
  cloze: 'Cloze',
  known: 'Know',
  skip: 'Skip',
}
