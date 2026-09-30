import type { CandidateStatus } from '@/api/types'

export type Decision = Exclude<CandidateStatus, 'pending'>

/** Новая оценка фразы или null, если она уже такая: вернуть фразу в «не оценено» API не позволяет. */
export function decisionChange(current: CandidateStatus, chosen: Decision): Decision | null {
  return current === chosen ? null : chosen
}
