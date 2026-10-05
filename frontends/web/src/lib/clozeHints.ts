import type { ClozeDefaultHint, ClozeHintKind } from '@/api/types'

export const CLOZE_HINT_LABEL: Record<ClozeHintKind, string> = {
  none: 'No hint',
  translation: 'Translation',
  synonyms: 'Synonyms',
  first_letter: 'First letter',
  custom: 'Custom',
}

const DEFAULT_HINT_KINDS: ClozeDefaultHint[] = ['none', 'translation', 'synonyms', 'first_letter']
const HINT_KINDS: ClozeHintKind[] = [...DEFAULT_HINT_KINDS, 'custom']

const options = <T extends ClozeHintKind>(kinds: T[]) => kinds.map(value => ({ value, label: CLOZE_HINT_LABEL[value] }))

export const CLOZE_HINT_OPTIONS = options(HINT_KINDS)
export const CLOZE_DEFAULT_HINT_OPTIONS = options(DEFAULT_HINT_KINDS)

/** Пропуск на лицевой стороне, которую рисует backend. */
export const CLOZE_GAP = '[…]'
