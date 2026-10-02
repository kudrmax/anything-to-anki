import { describe, expect, it } from 'vitest'
import type { StoredCandidate } from '@/api/types'
import { shownCandidates } from './useShownCandidates'

const candidates = (count: number) =>
  Array.from({ length: count }, (_, i) => ({ id: i + 1 }) as StoredCandidate)

const ids = (list: StoredCandidate[]) => list.map(c => c.id)

describe('shownCandidates', () => {
  it('shows the first page and counts the rest', () => {
    const result = shownCandidates(candidates(40), 15, 1, 1)
    expect(ids(result.shown)).toHaveLength(15)
    expect(result.hiddenCount).toBe(25)
    expect(result.nextPageCount).toBe(15)
  })

  it('the next page is smaller when few candidates are left', () => {
    const result = shownCandidates(candidates(20), 15, 1, 1)
    expect(result.nextPageCount).toBe(5)
  })

  it('shows more pages', () => {
    const result = shownCandidates(candidates(40), 15, 1, 2)
    expect(ids(result.shown)).toHaveLength(30)
    expect(result.hiddenCount).toBe(10)
  })

  it('extends to the current candidate when it is below the shown pages', () => {
    const result = shownCandidates(candidates(40), 15, 17, 1)
    expect(result.pages).toBe(2)
    expect(ids(result.shown)).toContain(17)
  })

  it('shows everything without a page size', () => {
    const result = shownCandidates(candidates(40), null, 1, 1)
    expect(ids(result.shown)).toHaveLength(40)
    expect(result.hiddenCount).toBe(0)
  })
})
