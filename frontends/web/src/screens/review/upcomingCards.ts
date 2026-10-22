import type { StoredCandidate } from '@/api/types'
import type { ReviewState } from './reviewState'

/** Загруженные карточки, что идут в списке следом за текущей: их готовят заранее. */
export function upcomingCards(state: ReviewState, count: number): StoredCandidate[] {
  const rows = [...state.rows.values()].sort((a, b) => a.index - b.index)
  const start = rows.findIndex(row => row.phrase_id !== null && row.phrase_id === state.currentId)
  if (start < 0) return []
  const upcoming: StoredCandidate[] = []
  for (const row of rows.slice(start + 1)) {
    const card = row.phrase_id === null ? undefined : state.cards.get(row.phrase_id)
    if (card) upcoming.push(card)
    if (upcoming.length === count) break
  }
  return upcoming
}
