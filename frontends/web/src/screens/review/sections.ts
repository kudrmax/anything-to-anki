import type { CandidateSection } from '@/api/types'

const SECTION_NOUN: Record<CandidateSection, [one: string, many: string]> = {
  ready: ['ready phrase', 'ready phrases'],
  extra: ['phrase with more new words', 'phrases with more new words'],
  probably_known: ['probably known word', 'probably known words'],
  reviewed: ['reviewed phrase', 'reviewed phrases'],
}

/** Кнопка раздела под списком: «Show 2 phrases with more new words» / «Hide …». */
export const sectionToggleLabel = (section: CandidateSection, count: number, open: boolean): string => {
  const [one, many] = SECTION_NOUN[section]
  const noun = count === 1 ? one : many
  return open ? `Hide ${many}` : `Show ${count} ${noun}`
}
