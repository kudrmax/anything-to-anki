import { describe, expect, it } from 'vitest'
import type { CandidateSection, StoredCandidate } from '@/api/types'
import { listItems, sectionToggleLabel, visibleCandidates } from './sections'

const card = (id: number, section: CandidateSection) => ({ phrase_id: id, section }) as StoredCandidate
const CARDS = [card(1, 'ready'), card(2, 'extra'), card(3, 'extra'), card(4, 'probably_known'), card(5, 'reviewed')]
const rows = (open: CandidateSection[], shownCount = CARDS.length) => {
  const opened = new Set(open)
  const shown = visibleCandidates(CARDS, opened).slice(0, shownCount)
  return listItems(CARDS, shown, opened).map(item => (item.kind === 'section' ? `${item.section}${item.open ? '-' : '+'}` : item.candidate.phrase_id))
}

describe('listItems', () => {
  it('folds every section under ready', () => {
    expect(rows([])).toEqual([1, 'extra+', 'probably_known+', 'reviewed+'])
  })

  it('shows the cards of an open section under its row', () => {
    expect(rows(['extra'])).toEqual([1, 'extra-', 2, 3, 'probably_known+', 'reviewed+'])
  })

  it('waits for the cards above before showing the next section', () => {
    expect(rows(['extra'], 2)).toEqual([1, 'extra-', 2])
  })

  it('puts the reviewed cards last, under their own row', () => {
    expect(rows(['reviewed'])).toEqual([1, 'extra+', 'probably_known+', 'reviewed-', 5])
  })
})

describe('sectionToggleLabel', () => {
  it('names the reviewed group', () => {
    expect(sectionToggleLabel('reviewed', 1, false)).toBe('Show 1 reviewed phrase')
    expect(sectionToggleLabel('reviewed', 3, true)).toBe('Hide reviewed phrases')
  })
})
