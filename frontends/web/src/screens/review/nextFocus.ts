import type { CandidateSection, StoredCandidate } from '@/api/types'

/**
 * Фраза, на которую переходим после решения. Порядок после решения меняет backend
 * (решённая уходит вниз, известные слова пересортировывают остальные), поэтому
 * берём ожидающую фразу, которая теперь стоит на месте решённой, — фокус не прыгает.
 * С разделом — только внутри него: разобрав Ready, пользователь не проваливается в остальные.
 */
export function nextFocusId(
  fresh: StoredCandidate[], markedId: number, markedIndex: number, section: CandidateSection | null = null,
): number | null {
  const isNext = (c: StoredCandidate) =>
    c.status === 'pending' && c.phrase_id !== markedId && (section === null || c.section === section)
  return (fresh.slice(markedIndex).find(isNext) ?? fresh.find(isNext))?.phrase_id ?? null
}
