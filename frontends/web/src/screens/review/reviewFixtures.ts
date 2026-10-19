import type { CardButton, CardState, DecisionButton, Shown, StoredCandidate } from '@/api/types'

const BUTTONS: DecisionButton[] = ['learn', 'cloze', 'known', 'skip']

/** Кнопки карточки, как их даёт backend: по умолчанию все решают, ни одна не нажата. */
export const buttons = (changes: Partial<Record<DecisionButton, Partial<CardButton>>> = {}): CardButton[] =>
  BUTTONS.map(button => ({ button, command: 'decide', pressed: false, refused: null, ...changes[button] }))

export const state = (changes: Partial<CardState> = {}): CardState =>
  ({ note: null, known_on: null, buttons: buttons(), ...changes })

const NEW: Shown = { status: 'new', skipped: false, where: 'nowhere', tone: 'open' }

/** Карточка ревью с тем, что читают экраны; остальное — как пришло бы пустым. */
export const reviewCard = (changes: Partial<StoredCandidate> = {}): StoredCandidate =>
  ({
    phrase_id: 1,
    word_id: 1,
    phrase: { text: 'He glared at me.', words: [[0, 2], [3, 9], [10, 12], [13, 16]], target: [1] },
    choice: 'none',
    shown: NEW,
    state: state(),
    is_done: false,
    cloze: null,
    can_edit_cloze: false,
    section: 'ready',
    ...changes,
  }) as StoredCandidate
