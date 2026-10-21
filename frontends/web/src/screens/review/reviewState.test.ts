import { describe, expect, it } from 'vitest'
import { cardRow, layout, reviewCard, reviewUpdate, sectionRow } from './reviewFixtures'
import { applyUpdate, forgetDone, initialState, listRows, neighbour, reopened, withCurrent, type ReviewState } from './reviewState'

const card = (id: number) => reviewCard({ phrase_id: id, word_id: id })
const loadedIds = (state: ReviewState) => [...state.rows.values()].map(r => r.phrase_id ?? r.section)

/** Открытое ревью: 100 строк, загружены 40–42 вокруг карточки 41. */
const opened = () => applyUpdate(initialState, reviewUpdate({
  revision: 5,
  layout: layout([cardRow(40, 40), cardRow(41, 41), cardRow(42, 42)], { total_rows: 100, total_cards: 100, replace: true }),
  cards: [card(40), card(41), card(42)],
  focus_id: 41,
}))

describe('applyUpdate', () => {
  it('ignores an update older than what the client knows', () => {
    const state = opened()
    const stale = reviewUpdate({ revision: 4, cards: [{ ...card(41), lemma: 'old' }], focus_id: 40 })
    expect(applyUpdate(state, stale)).toBe(state)
  })

  it('ignores an update of another review', () => {
    const state = opened()
    expect(applyUpdate(state, reviewUpdate({ review_id: 'other', revision: 9, focus_id: 40 }))).toBe(state)
  })

  it('merges rows by index and keeps the rows it had', () => {
    const state = applyUpdate(opened(), reviewUpdate({
      revision: 5, layout: layout([cardRow(0, 1), cardRow(1, 2)], { total_rows: 100, total_cards: 100 }), cards: [card(1), card(2)],
    }), { window: true })
    expect([...state.rows.keys()].sort((a, b) => a - b)).toEqual([0, 1, 40, 41, 42])
    expect(state.cards.size).toBe(5)
  })

  it('on replace keeps only the rows and cards it was sent', () => {
    const state = applyUpdate(opened(), reviewUpdate({
      revision: 6,
      layout: layout([cardRow(10, 41), sectionRow(11, 'extra', 3, true)], { version: 1, total_rows: 30, total_cards: 29, replace: true }),
      cards: [card(41)],
    }))
    expect(loadedIds(state)).toEqual([41, 'extra'])
    expect([...state.cards.keys()]).toEqual([41])
    expect(state).toMatchObject({ version: 1, totalRows: 30, totalCards: 29 })
  })

  it('drops a layout older than the one it has', () => {
    const state = applyUpdate(opened(), reviewUpdate({
      revision: 6, layout: layout([cardRow(5, 41)], { version: 2, total_rows: 10, replace: true }), cards: [card(41)],
    }))
    const late = applyUpdate(state, reviewUpdate({ revision: 6, layout: layout([cardRow(0, 99)], { version: 1, total_rows: 100 }) }))
    expect(loadedIds(late)).toEqual([41])
    expect(late.totalRows).toBe(10)
  })

  it('takes removed cards out of the rows and the cards', () => {
    const state = applyUpdate(opened(), reviewUpdate({ revision: 6, removed: [42] }))
    expect(loadedIds(state)).toEqual([40, 41])
    expect(state.cards.has(42)).toBe(false)
  })

  it('takes the focus only when the update gives one', () => {
    const moved = applyUpdate(opened(), reviewUpdate({ revision: 6, focus_id: 42 }))
    expect(moved.currentId).toBe(42)
    expect(applyUpdate(moved, reviewUpdate({ revision: 7 })).currentId).toBe(42)
  })

  it('merges done with the revision it came at', () => {
    const first = applyUpdate(opened(), reviewUpdate({ revision: 6, done: { 41: true, 7: true } }))
    const second = applyUpdate(first, reviewUpdate({ revision: 8, done: { 41: false } }))
    expect(Object.fromEntries(second.done)).toEqual({ 41: { done: false, revision: 8 }, 7: { done: true, revision: 6 } })
  })

  it('a window read keeps the revision the client sends as since', () => {
    const state = applyUpdate(opened(), reviewUpdate({ revision: 9, layout: layout([cardRow(0, 1)], { total_rows: 100 }), cards: [card(1)] }), { window: true })
    expect(state.revision).toBe(5)
    expect(state.cards.has(1)).toBe(true)
  })

  it('takes the header of every update', () => {
    const state = applyUpdate(opened(), reviewUpdate({ revision: 6, header: { ...reviewUpdate().header, busy: true } }))
    expect(state.header?.busy).toBe(true)
  })
})

describe('reopened', () => {
  it('starts over on the new review and keeps the done marks for the text', () => {
    const state = applyUpdate(opened(), reviewUpdate({ revision: 6, done: { 41: true } }))
    const again = reopened(state, reviewUpdate({
      review_id: 'r2', revision: 2, layout: layout([cardRow(0, 41)], { replace: true }), cards: [card(41)], focus_id: 41,
    }))
    expect(again).toMatchObject({ reviewId: 'r2', revision: 2, currentId: 41, totalRows: 1 })
    expect(again.done.get(41)?.done).toBe(true)
  })
})

describe('forgetDone', () => {
  it('drops the marks a text read at that revision already holds', () => {
    const state = applyUpdate(applyUpdate(opened(), reviewUpdate({ revision: 6, done: { 1: true } })), reviewUpdate({ revision: 8, done: { 2: true } }))
    expect([...forgetDone(state, 6).done.keys()]).toEqual([2])
  })
})

describe('neighbour', () => {
  const state = withCurrent(applyUpdate(initialState, reviewUpdate({
    layout: layout([cardRow(0, 1, 1), sectionRow(1, 'extra', 1, true), cardRow(2, 2, 2), cardRow(5, 5, 5)], { total_rows: 6, total_cards: 5 }),
    cards: [card(1), card(2), card(5)],
  })), 1)

  it('steps over section rows to the next position', () => {
    expect(neighbour(state, 1)).toBe(2)
  })

  it('says there is no card before the first', () => {
    expect(neighbour(state, -1)).toBeNull()
  })

  it('says the rows in between are not loaded yet', () => {
    expect(neighbour(withCurrent(state, 2), 1)).toBeUndefined()
  })
})

describe('listRows', () => {
  it('folds every run of rows not loaded into one gap', () => {
    const state = applyUpdate(initialState, reviewUpdate({ layout: layout([cardRow(3, 3), cardRow(4, 4)], { total_rows: 10 }) }))
    expect(listRows(state).map(item => ('end' in item ? `${item.start}-${item.end}` : item.index))).toEqual(['0-3', 3, 4, '5-10'])
  })
})
