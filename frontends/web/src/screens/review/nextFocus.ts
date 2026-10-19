import type { CandidateSection, StoredCandidate } from '@/api/types'

/**
 * Фраза, на которую переходим после решения. Нажатая карточка остаётся на месте до перезагрузки
 * списка, поэтому берём следующую открытую под ней.
 * С разделом — только внутри него: разобрав Ready, пользователь не проваливается в остальные.
 */
export function nextFocusId(
  fresh: StoredCandidate[], markedId: number, markedIndex: number, section: CandidateSection | null = null,
): number | null {
  const isNext = (c: StoredCandidate) =>
    !c.is_done && c.phrase_id !== markedId && (section === null || c.section === section)
  return (fresh.slice(markedIndex).find(isNext) ?? fresh.find(isNext))?.phrase_id ?? null
}

/** Фокус уходит, только когда нажатая карточка стала разобранной; разобрана ли она, решает backend. */
export function focusAfterPress(
  fresh: StoredCandidate[], markedId: number, wasDone: boolean, section: CandidateSection | null = null,
): number | null {
  const markedIndex = fresh.findIndex(c => c.phrase_id === markedId)
  if (wasDone || markedIndex < 0 || !fresh[markedIndex].is_done) return null
  return nextFocusId(fresh, markedId, markedIndex, section)
}
