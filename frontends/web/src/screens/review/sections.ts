import type { CandidateSection, StoredCandidate } from '@/api/types'

/** Разделы под Ready: свёрнуты, пока их не открыли. */
export const FOLDED_SECTIONS: CandidateSection[] = ['extra', 'probably_known']

const SECTION_NOUN: Record<CandidateSection, [one: string, many: string]> = {
  ready: ['ready phrase', 'ready phrases'],
  extra: ['phrase with more new words', 'phrases with more new words'],
  probably_known: ['probably known word', 'probably known words'],
}

/** Кнопка раздела под списком: «Show 2 phrases with more new words» / «Hide …». */
export const sectionToggleLabel = (section: CandidateSection, count: number, open: boolean): string => {
  const [one, many] = SECTION_NOUN[section]
  const noun = count === 1 ? one : many
  return open ? `Hide ${many}` : `Show ${count} ${noun}`
}

export type ListItem =
  | { kind: 'candidate'; candidate: StoredCandidate }
  | { kind: 'section'; section: CandidateSection; count: number; open: boolean }

const isReady = (c: StoredCandidate) => c.section === null || c.section === 'ready'

/** Карточки, которые видны в списке: Ready и открытые разделы. */
export const visibleCandidates = (candidates: StoredCandidate[], open: ReadonlySet<CandidateSection>): StoredCandidate[] =>
  candidates.filter(c => isReady(c) || (c.section !== null && open.has(c.section)))

/**
 * Строки списка: показанные карточки Ready, под ними строка каждого свёрнутого раздела,
 * а у открытого — его карточки под его строкой. Строка раздела появляется, когда показано всё, что выше.
 */
export function listItems(
  candidates: StoredCandidate[], shown: StoredCandidate[], open: ReadonlySet<CandidateSection>,
): ListItem[] {
  const shownIds = new Set(shown.map(c => c.phrase_id))
  const ready = candidates.filter(isReady)
  const items: ListItem[] = ready.filter(c => shownIds.has(c.phrase_id)).map(candidate => ({ kind: 'candidate', candidate }))
  let reached = ready.every(c => shownIds.has(c.phrase_id))
  for (const section of FOLDED_SECTIONS) {
    const cards = candidates.filter(c => c.section === section)
    if (!reached || cards.length === 0) continue
    const isOpen = open.has(section)
    items.push({ kind: 'section', section, count: cards.length, open: isOpen })
    if (!isOpen) continue
    items.push(...cards.filter(c => shownIds.has(c.phrase_id)).map(candidate => ({ kind: 'candidate' as const, candidate })))
    reached = cards.every(c => shownIds.has(c.phrase_id))
  }
  return items
}
