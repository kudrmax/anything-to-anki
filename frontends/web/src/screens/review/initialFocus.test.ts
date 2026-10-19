import { describe, expect, it } from 'vitest'
import type { CandidateStatus, StoredCandidate } from '@/api/types'
import { initialFocusId } from './initialFocus'

// Как отдаёт backend: открытые карточки сверху, разобранные — в Reviewed внизу.
const list = (...items: [number, CandidateStatus][]) =>
  items.map(([id, status]) =>
    ({ phrase_id: id, status, is_done: status !== 'pending', section: status === 'pending' ? 'ready' : 'reviewed' }) as StoredCandidate)

describe('initialFocusId', () => {
  it('opens the card the link asks for, even a reviewed one', () => {
    expect(initialFocusId(list([1, 'pending'], [2, 'learn']), 2)).toBe(2)
  })

  it('falls back to the first open card when the link points elsewhere', () => {
    expect(initialFocusId(list([2, 'pending'], [1, 'known']), 99)).toBe(2)
  })

  it('takes the first open card without a link', () => {
    expect(initialFocusId(list([2, 'pending'], [3, 'pending'], [1, 'known']), null)).toBe(2)
  })

  it('opens the first reviewed card when every card is done', () => {
    expect(initialFocusId(list([1, 'known'], [2, 'skip']), null)).toBe(1)
  })

  it('passes over a card done via another source', () => {
    const doneElsewhere = { phrase_id: 1, status: 'pending', is_done: true, section: 'reviewed' } as StoredCandidate
    expect(initialFocusId([...list([2, 'pending']), doneElsewhere], null)).toBe(2)
  })
})
