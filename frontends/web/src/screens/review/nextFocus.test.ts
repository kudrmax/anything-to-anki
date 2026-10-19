import { describe, expect, it } from 'vitest'
import type { CandidateSection, CandidateStatus, StoredCandidate } from '@/api/types'
import { focusAfterPress, nextFocusId } from './nextFocus'

// Порядок и разделы сняты при загрузке: нажатая карточка остаётся на месте, разобранные внизу — в Reviewed.
const list = (...items: [number, CandidateStatus, CandidateSection?][]) =>
  items.map(([id, status, section = status === 'pending' ? 'ready' : 'reviewed']) =>
    ({ phrase_id: id, status, is_done: status !== 'pending', section }) as StoredCandidate)

describe('nextFocusId', () => {
  it('takes the next open phrase below the marked one, which stays in place', () => {
    const fresh = list([1, 'pending'], [2, 'known', 'ready'], [5, 'pending'], [3, 'pending'])
    expect(nextFocusId(fresh, 2, 1)).toBe(5)
  })

  it('skips done phrases below it', () => {
    const fresh = list([1, 'pending'], [2, 'learn', 'ready'], [4, 'skip', 'ready'], [3, 'pending'])
    expect(nextFocusId(fresh, 2, 1)).toBe(3)
  })

  it('wraps to the first open phrase when none is left below', () => {
    const fresh = list([1, 'pending'], [2, 'learn', 'ready'], [3, 'known'])
    expect(nextFocusId(fresh, 2, 1)).toBe(1)
  })

  it('never returns the marked phrase itself', () => {
    const fresh = list([2, 'pending'], [1, 'known'])
    expect(nextFocusId(fresh, 2, 0)).toBeNull()
  })

  it('returns null when nothing is open', () => {
    expect(nextFocusId(list([1, 'known'], [2, 'skip']), 2, 1)).toBeNull()
  })

  it('stays in the section of the marked phrase', () => {
    const fresh = list([1, 'learn', 'ready'], [2, 'pending', 'extra'], [3, 'known'])
    expect(nextFocusId(fresh, 1, 0, 'ready')).toBeNull()
    expect(nextFocusId(fresh, 1, 0)).toBe(2)
  })
})

describe('focusAfterPress', () => {
  it('moves on when the pressed card became done', () => {
    const fresh = list([1, 'learn', 'ready'], [2, 'pending'], [3, 'known'])
    expect(focusAfterPress(fresh, 1, false, 'ready')).toBe(2)
  })

  it('stays when the card was done already', () => {
    const fresh = list([1, 'known', 'ready'], [2, 'pending'])
    expect(focusAfterPress(fresh, 1, true, 'ready')).toBeNull()
  })

  it('stays when the card is open again', () => {
    const fresh = list([1, 'pending', 'reviewed'], [2, 'pending'])
    expect(focusAfterPress(fresh, 1, true, 'reviewed')).toBeNull()
  })

  it('stays when the card is gone from the list', () => {
    expect(focusAfterPress(list([2, 'pending']), 1, false, 'ready')).toBeNull()
  })
})
