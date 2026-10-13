import type { CandidateSection, StoredCandidate } from '@/api/types'

export const SECTION_LABEL: Record<CandidateSection, string> = {
  ready: 'Ready',
  extra: 'Extra new words',
  probably_known: 'Probably known',
}

export type ListItem =
  | { kind: 'candidate'; candidate: StoredCandidate }
  | { kind: 'section'; section: CandidateSection }

/** Кандидаты списка с подписью перед первым кандидатом каждого раздела после Ready. */
export function withSectionLabels(shown: StoredCandidate[]): ListItem[] {
  const items: ListItem[] = []
  let previous: CandidateSection | null = 'ready'
  for (const candidate of shown) {
    const section = candidate.section
    if (section !== null && section !== previous) items.push({ kind: 'section', section })
    previous = section
    items.push({ kind: 'candidate', candidate })
  }
  return items
}

export const countIn = (candidates: StoredCandidate[], section: CandidateSection): number =>
  candidates.filter(c => c.section === section).length
