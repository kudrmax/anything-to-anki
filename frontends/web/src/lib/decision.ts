import type { CandidateStatus } from '@/api/types'

export type Decision = Exclude<CandidateStatus, 'pending'>

/** Новая оценка фразы; повторный выбор той же оценки отменяет её. */
export function decisionChange(current: CandidateStatus, chosen: Decision): CandidateStatus {
  return current === chosen ? 'pending' : chosen
}
