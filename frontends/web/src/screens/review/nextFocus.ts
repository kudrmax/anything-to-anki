import type { StoredCandidate } from '@/api/types'

/**
 * Фраза, на которую переходим после решения. Порядок после решения меняет backend
 * (решённая уходит вниз, известные слова пересортировывают остальные), поэтому
 * берём ожидающую фразу, которая теперь стоит на месте решённой, — фокус не прыгает.
 */
export function nextFocusId(fresh: StoredCandidate[], markedId: number, markedIndex: number): number | null {
  const isNext = (c: StoredCandidate) => c.status === 'pending' && c.id !== markedId
  return (fresh.slice(markedIndex).find(isNext) ?? fresh.find(isNext))?.id ?? null
}
