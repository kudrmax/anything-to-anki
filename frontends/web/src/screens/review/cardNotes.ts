import type { CardNote, CardState } from '@/api/types'
import { formatDay } from '@/lib/text/format'

/** Пометка слова Known по 30 дням в Anki: на карточке и в списке Known. */
export const TIMER_KNOWN_LABEL = 'Known: 30 days in Anki'

/** Подписи карточек — все в одном месте; какую показать, решает backend. */
export const CARD_NOTE_LABEL: Record<CardNote, string> = {
  learned_on_other_card: 'Learned via other phrase',
  known_on_other_card: 'Known via other phrase',
  known_elsewhere: 'Known',
  learning_elsewhere: 'Learning from another source',
  learn_elsewhere: 'Learn in another source',
  in_anki: 'In Anki',
  known_by_timer: TIMER_KNOWN_LABEL,
  known_by_list: 'In your Known words',
}

export const KNOWN_ON_LABEL = 'Known on'

/** Подпись как её дал backend, с датой, если она есть. */
export function cardNoteText({ note, known_on: knownOn }: Pick<CardState, 'note' | 'known_on'>): string | null {
  if (note === null) return null
  return knownOn ? `${CARD_NOTE_LABEL[note]} · ${KNOWN_ON_LABEL} ${formatDay(knownOn)}` : CARD_NOTE_LABEL[note]
}
