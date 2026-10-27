import type { CandidateSection, CardButton, CardState, DecisionButton, ReviewHeader, ReviewLayout, ReviewRow, ReviewUpdate, Shown, StoredCandidate } from '@/api/types'

const BUTTONS: DecisionButton[] = ['learn', 'cloze', 'known', 'skip']

/** Кнопки карточки, как их даёт backend: по умолчанию все решают, ни одна не нажата; Skip закрывает карточку, остальные — лемму. */
export const buttons = (changes: Partial<Record<DecisionButton, Partial<CardButton>>> = {}): CardButton[] =>
  BUTTONS.map(button => ({
    button, command: 'decide', pressed: false, refused: null, closes: button === 'skip' ? 'card' : 'lemma', ...changes[button],
  }))

export const state = (changes: Partial<CardState> = {}): CardState =>
  ({ buttons: buttons(), ...changes })

const GLARED = { text: 'He glared at me.', words: [[0, 2], [3, 9], [10, 12], [13, 16]], target: [1] } as StoredCandidate['phrase']

const NEW: Shown = { status: 'new', skipped: false, where: 'nowhere', tone: 'open' }

/** Карточка ревью с тем, что читают экраны; остальное — как пришло бы пустым. */
export const reviewCard = (changes: Partial<StoredCandidate> = {}): StoredCandidate =>
  ({
    phrase_id: 1,
    word_id: 1,
    phrase: GLARED,
    source_phrase: GLARED,
    phrase_position: null,
    choice: 'none',
    shown: NEW,
    state: state(),
    is_done: false,
    cloze: null,
    can_edit_cloze: false,
    section: 'ready',
    source: { id: 1, has_video: false, can_polish_phrases: false },
    ...changes,
  }) as StoredCandidate

export const REVIEW_ID = 'r1'

export const header = (changes: Partial<ReviewHeader> = {}): ReviewHeader => ({
  scope: 'source-7', title: 'Pilot', status: 'partially_reviewed', progress: { decided: 0, total: 0 },
  learn_count: 0, busy: false, ...changes,
}) as ReviewHeader

/** Строка карточки: позиция по умолчанию — номер строки + 1. */
export const cardRow = (index: number, phraseId: number, position = index + 1): ReviewRow =>
  ({ index, kind: 'card', phrase_id: phraseId, position, section: null, count: null, open: null })

export const sectionRow = (index: number, section: CandidateSection, count: number, open = false): ReviewRow =>
  ({ index, kind: 'section', phrase_id: null, position: null, section, count, open })

export const layout = (rows: ReviewRow[], changes: Partial<ReviewLayout> = {}): ReviewLayout =>
  ({ version: 0, total_rows: rows.length, total_cards: rows.filter(r => r.kind === 'card').length, replace: false, rows, ...changes })

/** Ответ ревью: по умолчанию ничего не изменилось. */
export const reviewUpdate = (changes: Partial<ReviewUpdate> = {}): ReviewUpdate => ({
  review_id: REVIEW_ID, revision: 1, header: header(), layout: null, cards: [], removed: [], done: {}, focus_id: null, undo: null,
  text: null, highlights: [], contents_version: 0, ...changes,
})
