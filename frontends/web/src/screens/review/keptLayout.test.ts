import { describe, expect, it } from 'vitest'
import type { CandidateSection, StoredCandidate } from '@/api/types'
import { keepLayout } from './keptLayout'
import { listItems, visibleCandidates } from './sections'

const card = (id: number, section: CandidateSection, isDone = section === 'reviewed') =>
  ({ phrase_id: id, section, is_done: isDone, choice: isDone ? 'learn' : 'none' }) as StoredCandidate

const ids = (cards: StoredCandidate[]) => cards.map(c => c.phrase_id)
const groups = (cards: StoredCandidate[]) => {
  const open = new Set<CandidateSection>(['extra', 'probably_known', 'reviewed'])
  return listItems(cards, visibleCandidates(cards, open), open)
    .map(item => (item.kind === 'section' ? item.section : item.candidate.phrase_id))
}

// При загрузке: 1 и 2 в Ready, 3 в Extra, 4 уже разобрана.
const LOADED = [card(1, 'ready'), card(2, 'ready'), card(3, 'extra'), card(4, 'reviewed')]
// Ответ backend после нажатия на 1: она разобрана и стоит в Reviewed.
const AFTER_PRESS = [card(2, 'ready'), card(3, 'extra'), card(1, 'reviewed'), card(4, 'reviewed')]

describe('keepLayout', () => {
  it('keeps the pressed card where it stood until the list reloads', () => {
    const kept = keepLayout(LOADED, AFTER_PRESS)
    expect(ids(kept)).toEqual([1, 2, 3, 4])
    expect(groups(kept)).toEqual([1, 2, 'extra', 3, 'reviewed', 4])
  })

  it('takes the fresh data of every card', () => {
    const pressed = keepLayout(LOADED, AFTER_PRESS).find(c => c.phrase_id === 1)
    expect(pressed?.is_done).toBe(true)
    expect(pressed?.choice).toBe('learn')
  })

  it('drops a card that is no longer shown', () => {
    expect(ids(keepLayout(LOADED, [card(1, 'ready'), card(3, 'extra'), card(4, 'reviewed')]))).toEqual([1, 3, 4])
  })

  it('puts a new card after the card it follows in the fresh list', () => {
    const fresh = [card(5, 'ready'), card(1, 'ready'), card(6, 'ready'), card(2, 'ready'), card(3, 'extra'), card(4, 'reviewed')]
    expect(ids(keepLayout(LOADED, fresh))).toEqual([5, 1, 6, 2, 3, 4])
    expect(keepLayout(LOADED, fresh).find(c => c.phrase_id === 6)?.section).toBe('ready')
  })

  it('arranges the first load as the backend did', () => {
    expect(keepLayout([], AFTER_PRESS)).toEqual(AFTER_PRESS)
  })
})
