import type { CandidateStatus, StoredCandidate } from '@/api/types'

export type Decision = Exclude<CandidateStatus, 'pending'>

/**
 * Новая оценка фразы; повторный выбор той же оценки отменяет её.
 * Learn на cloze-карточке, которую ещё можно менять, не отменяет оценку, а делает карточку обычной.
 */
export function decisionChange(current: CandidateStatus, chosen: Decision, convertsCloze = false): CandidateStatus {
  if (convertsCloze && chosen === 'learn') return 'learn'
  return current === chosen ? 'pending' : chosen
}

/** Learn превращает cloze-карточку в обычную, только пока она не в Anki (`can_cloze`). */
export function learnConvertsCloze(candidate: Pick<StoredCandidate, 'cloze' | 'can_cloze'>): boolean {
  return candidate.cloze !== null && candidate.can_cloze
}
