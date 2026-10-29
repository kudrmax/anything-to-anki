import { describe, expect, it } from 'vitest'
import type { StoredCandidate } from '@/api/types'
import { buttons, cardRow, layout, reviewCard, reviewUpdate, state } from './reviewFixtures'
import { applyUpdate, initialState } from './reviewState'
import { cardsUnder } from './swipeStack'

const card = (id: number, lemma: string, changes: Partial<StoredCandidate> = {}) =>
  reviewCard({ phrase_id: id, word_id: id, lemma, ...changes })

/** Три карточки подряд, текущая — первая; у первых двух одна лемма. */
const opened = (first: StoredCandidate) => {
  const cards = [first, card(2, 'tie'), card(3, 'aura')]
  return applyUpdate(initialState, reviewUpdate({
    revision: 5,
    layout: layout(cards.map((c, i) => cardRow(i, c.phrase_id)), { total_rows: 3, total_cards: 3, replace: true }),
    cards,
    focus_id: 1,
  }))
}

describe('cardsUnder', () => {
  it('Learn and Know close the lemma, Skip only the card: each has its own card underneath', () => {
    const current = card(1, 'tie')
    expect(cardsUnder(opened(current), current)).toEqual(new Map([[3, ['right', 'left']], [2, ['down']]]))
  })

  it('a decision already taken leads to the next card of the list', () => {
    const current = card(1, 'tie', { state: state({ buttons: buttons({ learn: { pressed: true } }) }) })
    expect(cardsUnder(opened(current), current).get(2)).toEqual(['right', 'down'])
  })

  it('a refused decision has no card underneath', () => {
    const current = card(1, 'tie', { state: state({ buttons: buttons({ skip: { command: null, refused: 'not_decision_card' } }) }) })
    expect([...cardsUnder(opened(current), current).values()].flat()).not.toContain('down')
  })
})
