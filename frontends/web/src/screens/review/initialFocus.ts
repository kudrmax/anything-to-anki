import type { StoredCandidate } from '@/api/types'

const firstPendingId = (candidates: StoredCandidate[]): number | null =>
  (candidates.find(c => !c.is_done) ?? candidates[0])?.phrase_id ?? null

/** Карточка, с которой открывается ревью: запрошенная ссылкой, если она есть в источнике, иначе первая неразобранная. */
export const initialFocusId = (candidates: StoredCandidate[], requestedId: number | null): number | null =>
  candidates.some(c => c.phrase_id === requestedId) ? requestedId : firstPendingId(candidates)
