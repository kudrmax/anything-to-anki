import { describe, expect, it } from 'vitest'
import type { StoredCandidate } from '@/api/types'
import { initialFocusId } from './initialFocus'

/** Что сделано с карточкой в фикстуре: open — открыта, остальное — разобрана. */
type Mark = 'open' | 'learn' | 'known' | 'skip'

// Как отдаёт backend: открытые карточки сверху, разобранные — в Reviewed внизу.
const list = (...items: [number, Mark][]) =>
  items.map(([id, status]) =>
    ({ phrase_id: id, is_done: status !== 'open', section: status === 'open' ? 'ready' : 'reviewed' }) as StoredCandidate)

describe('initialFocusId', () => {
  it('opens the card the link asks for, even a reviewed one', () => {
    expect(initialFocusId(list([1, 'open'], [2, 'learn']), 2)).toBe(2)
  })

  it('falls back to the first open card when the link points elsewhere', () => {
    expect(initialFocusId(list([2, 'open'], [1, 'known']), 99)).toBe(2)
  })

  it('takes the first open card without a link', () => {
    expect(initialFocusId(list([2, 'open'], [3, 'open'], [1, 'known']), null)).toBe(2)
  })

  it('opens the first reviewed card when every card is done', () => {
    expect(initialFocusId(list([1, 'known'], [2, 'skip']), null)).toBe(1)
  })

  it('passes over a card done via another source', () => {
    const doneElsewhere = { phrase_id: 1, is_done: true, section: 'reviewed' } as StoredCandidate
    expect(initialFocusId([...list([2, 'open']), doneElsewhere], null)).toBe(2)
  })
})
