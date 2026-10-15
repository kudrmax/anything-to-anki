import type { CardState } from '@/api/types'

/** Скрытые слова cloze-карточки меняются там, где кнопка Cloze что-то делает; решает backend. */
export const canEditCloze = (state: CardState): boolean =>
  state.buttons.some(button => button.button === 'cloze' && button.action !== null)
