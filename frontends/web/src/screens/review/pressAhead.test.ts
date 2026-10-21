import { describe, expect, it } from 'vitest'
import type { ReviewRow, StoredCandidate } from '@/api/types'
import { pressAhead, undoAhead } from './pressAhead'
import { cardRow, layout, reviewCard, reviewUpdate, sectionRow } from './reviewFixtures'
import { applyUpdate, initialState, type ReviewState } from './reviewState'

const card = (id: number, changes: Partial<StoredCandidate> = {}) =>
  reviewCard({ phrase_id: id, word_id: id, lemma: `w${id}`, ...changes })

const opened = (rows: ReviewRow[], cards: StoredCandidate[], focus: number, totalRows = rows.length): ReviewState =>
  applyUpdate(initialState, reviewUpdate({
    revision: 5,
    layout: layout(rows, { total_rows: totalRows, total_cards: totalRows, replace: true }),
    cards,
    focus_id: focus,
  }))

/** Пять карточек подряд, текущая — первая. */
const five = (changes: Record<number, Partial<StoredCandidate>> = {}) =>
  opened([1, 2, 3, 4, 5].map(id => cardRow(id - 1, id)), [1, 2, 3, 4, 5].map(id => card(id, changes[id])), 1)

describe('pressAhead', () => {
  it('moves to the next open card and marks the pressed one done', () => {
    const shown = pressAhead(five(), 1, 'card')!
    expect(shown.state.currentId).toBe(2)
    expect(shown.state.done.get(1)?.done).toBe(true)
    expect(shown.ahead).toMatchObject({ pressed: 1, landed: 2 })
  })

  it('a press that closes the lemma marks every loaded card of it and skips them', () => {
    const state = five({ 2: { lemma: 'w1' }, 3: { lemma: 'w1' }, 5: { lemma: 'w1' } })
    const shown = pressAhead(state, 1, 'lemma')!
    expect(shown.state.currentId).toBe(4)
    expect([...shown.state.done.keys()].sort()).toEqual([1, 2, 3, 5])
  })

  it('a Skip closes only the card: the next card of the same lemma comes next', () => {
    const shown = pressAhead(five({ 2: { lemma: 'w1' } }), 1, 'card')!
    expect(shown.state.currentId).toBe(2)
  })

  it('skips cards already done and wraps to the top of the run; with none open it stays, as the server does', () => {
    const shown = pressAhead(five({ 1: { is_done: true }, 2: { is_done: true }, 4: { is_done: true }, 5: { is_done: true } }), 3, 'card')!
    expect(shown.state.currentId).toBe(3)
    const wrapped = pressAhead(
      { ...five({ 2: { is_done: true }, 4: { is_done: true }, 5: { is_done: true } }), currentId: 3 }, 3, 'card',
    )!
    expect(wrapped.state.currentId).toBe(1)
  })

  it('stays within the section of the pressed card', () => {
    const rows = [cardRow(0, 1), cardRow(1, 2), sectionRow(2, 'extra', 1, true), cardRow(3, 3)]
    const state = opened(rows, [card(1), card(2, { is_done: true }), card(3)], 2)
    const shown = pressAhead(state, 1, 'card')!
    expect(shown.ahead.landed).toBe(1)
    expect(shown.state.currentId).toBe(1)
  })

  it('stays on the pressed card when rows on the way are not loaded: the answer moves it', () => {
    const state = opened([cardRow(0, 1), cardRow(1, 2)], [card(1), card(2, { is_done: true })], 1, 10)
    expect(pressAhead(state, 1, 'card')!.ahead.landed).toBe(1)
  })

  it('does nothing for a press that closes nothing or a card already done', () => {
    expect(pressAhead(five(), 1, null)).toBeNull()
    expect(pressAhead(five({ 1: { is_done: true } }), 1, 'lemma')).toBeNull()
  })

  it('undo takes back its marks and returns to the pressed card, but keeps marks an answer set since', () => {
    const state = five({ 2: { lemma: 'w1' } })
    const shown = pressAhead(state, 1, 'lemma')!
    const answered = { ...shown.state, done: new Map(shown.state.done).set(2, { done: true, revision: 6 }) }
    const undone = undoAhead(answered, shown.ahead)
    expect(undone.currentId).toBe(1)
    expect(undone.done.has(1)).toBe(false)
    expect(undone.done.get(2)).toEqual({ done: true, revision: 6 })
  })
})
