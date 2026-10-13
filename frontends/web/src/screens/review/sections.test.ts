import { describe, expect, it } from 'vitest'
import type { CandidateSection, StoredCandidate } from '@/api/types'
import { listItems, visibleCandidates } from './sections'

const card = (id: number, section: CandidateSection) => ({ id, section }) as StoredCandidate
const CARDS = [card(1, 'ready'), card(2, 'extra'), card(3, 'extra'), card(4, 'probably_known')]
const rows = (open: CandidateSection[], shownCount = CARDS.length) => {
  const opened = new Set(open)
  const shown = visibleCandidates(CARDS, opened).slice(0, shownCount)
  return listItems(CARDS, shown, opened).map(item => (item.kind === 'section' ? `${item.section}${item.open ? '-' : '+'}` : item.candidate.id))
}

describe('listItems', () => {
  it('folds every section under ready', () => {
    expect(rows([])).toEqual([1, 'extra+', 'probably_known+'])
  })

  it('shows the cards of an open section under its row', () => {
    expect(rows(['extra'])).toEqual([1, 'extra-', 2, 3, 'probably_known+'])
  })

  it('waits for the cards above before showing the next section', () => {
    expect(rows(['extra'], 2)).toEqual([1, 'extra-', 2])
  })
})
