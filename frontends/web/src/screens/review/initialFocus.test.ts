import { describe, expect, it } from 'vitest'
import type { CandidateStatus, StoredCandidate } from '@/api/types'
import { initialFocusId } from './initialFocus'

const list = (...items: [number, CandidateStatus][]) =>
  items.map(([id, status]) => ({ phrase_id: id, status, is_done: status !== 'pending' }) as StoredCandidate)

describe('initialFocusId', () => {
  it('opens the card the link asks for, even a decided one', () => {
    expect(initialFocusId(list([1, 'pending'], [2, 'learn']), 2)).toBe(2)
  })

  it('falls back to the first pending card when the link points elsewhere', () => {
    expect(initialFocusId(list([1, 'known'], [2, 'pending']), 99)).toBe(2)
  })

  it('takes the first pending card without a link', () => {
    expect(initialFocusId(list([1, 'known'], [2, 'pending']), null)).toBe(2)
  })

  it('passes over a card done via another source', () => {
    const doneElsewhere = { phrase_id: 1, status: 'pending', is_done: true } as StoredCandidate
    expect(initialFocusId([doneElsewhere, ...list([2, 'pending'])], null)).toBe(2)
  })
})
