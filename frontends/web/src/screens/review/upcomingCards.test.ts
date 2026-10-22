import { describe, expect, it } from 'vitest'
import type { StoredCandidate } from '@/api/types'
import { cardRow, reviewCard, sectionRow } from './reviewFixtures'
import { initialState, type ReviewState } from './reviewState'
import { upcomingCards } from './upcomingCards'

const withRows = (rows: ReturnType<typeof cardRow>[], cards: StoredCandidate[], currentId: number): ReviewState => ({
  ...initialState,
  rows: new Map(rows.map(row => [row.index, row])),
  cards: new Map(cards.map(card => [card.phrase_id, card])),
  currentId,
})

const ids = (cards: StoredCandidate[]) => cards.map(card => card.phrase_id)

describe('upcomingCards', () => {
  const cards = [1, 2, 3, 4].map(id => reviewCard({ phrase_id: id }))

  it('takes the cards that follow the current one in list order', () => {
    const state = withRows([cardRow(2, 3), cardRow(0, 1), cardRow(1, 2), cardRow(3, 4)], cards, 2)
    expect(ids(upcomingCards(state, 5))).toEqual([3, 4])
  })

  it('stops at the asked count and skips section rows', () => {
    const state = withRows([cardRow(0, 1), sectionRow(1, 'ready', 3), cardRow(2, 2), cardRow(3, 3), cardRow(4, 4)], cards, 1)
    expect(ids(upcomingCards(state, 2))).toEqual([2, 3])
  })

  it('skips rows whose card is not loaded yet', () => {
    const state = withRows([cardRow(0, 1), cardRow(1, 9), cardRow(2, 2)], cards, 1)
    expect(ids(upcomingCards(state, 5))).toEqual([2])
  })

  it('is empty when the current card is not in the list', () => {
    expect(upcomingCards(withRows([cardRow(0, 1)], cards, 7), 5)).toEqual([])
  })
})
