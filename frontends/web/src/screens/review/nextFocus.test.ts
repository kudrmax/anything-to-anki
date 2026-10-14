import { describe, expect, it } from 'vitest'
import type { CandidateStatus, StoredCandidate } from '@/api/types'
import { nextFocusId } from './nextFocus'

const list = (...items: [number, CandidateStatus][]) =>
  items.map(([id, status]) => ({ phrase_id: id, status, is_done: status !== 'pending' }) as StoredCandidate)

describe('nextFocusId', () => {
  it('takes the pending phrase that now stands where the marked one stood', () => {
    // 2 помечена и ушла вниз; на её место после пересортировки встала 5
    const fresh = list([1, 'known'], [5, 'pending'], [3, 'pending'], [2, 'known'])
    expect(nextFocusId(fresh, 2, 1)).toBe(5)
  })

  it('skips decided phrases below that position', () => {
    const fresh = list([1, 'pending'], [4, 'skip'], [3, 'pending'], [2, 'learn'])
    expect(nextFocusId(fresh, 2, 1)).toBe(3)
  })

  it('wraps to the first pending phrase when none is left below', () => {
    const fresh = list([1, 'pending'], [3, 'known'], [2, 'learn'])
    expect(nextFocusId(fresh, 2, 2)).toBe(1)
  })

  it('never returns the marked phrase itself', () => {
    const fresh = list([2, 'pending'], [1, 'known'])
    expect(nextFocusId(fresh, 2, 0)).toBeNull()
  })

  it('returns null when nothing is pending', () => {
    expect(nextFocusId(list([1, 'known'], [2, 'skip']), 2, 0)).toBeNull()
  })

  it('stays in the section of the marked phrase', () => {
    const fresh = [
      { phrase_id: 1, status: 'learn', is_done: true, section: 'ready' },
      { phrase_id: 2, status: 'pending', is_done: false, section: 'extra' },
    ] as StoredCandidate[]
    expect(nextFocusId(fresh, 1, 0, 'ready')).toBeNull()
    expect(nextFocusId(fresh, 1, 0)).toBe(2)
  })
})
