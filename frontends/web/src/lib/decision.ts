import type { CandidateStatus } from '@/api/types'

export type Decision = Exclude<CandidateStatus, 'pending'>

/**
 * Новая оценка фразы; повторный выбор той же оценки отменяет её.
 * Learn на cloze-карточке не отменяет оценку, а делает карточку обычной.
 */
export function decisionChange(current: CandidateStatus, chosen: Decision, isCloze = false): CandidateStatus {
  if (isCloze && chosen === 'learn') return 'learn'
  return current === chosen ? 'pending' : chosen
}
