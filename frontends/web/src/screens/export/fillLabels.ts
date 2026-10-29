import type { CardFillSkip, CardPreview, ExportFill, MissingCardPart } from '@/api/types'

const MISSING_LABEL: Record<MissingCardPart, string> = { meaning: 'No meaning', audio: 'No audio', cloze: 'No cloze words' }
const GENERATING_LABEL: Record<MissingCardPart, string> = {
  meaning: 'Generating meaning', audio: 'Generating audio', cloze: 'Generating cloze words',
}
/** Почему часть одной карточки не догенерировать. */
const CARD_SKIP_LABEL: Record<CardFillSkip, string> = {
  video_not_downloaded: 'video not downloaded',
  video_downloading: 'video still downloading',
  no_phrase_time: 'phrase not timed in the video',
  source_busy: 'source is busy',
  cloze_needs_choice: 'pick them on the card',
}
/** Сколько карточек и почему догенерация пропустит. */
const SECTION_SKIP_LABEL: Record<CardFillSkip, string> = {
  video_not_downloaded: 'without the video',
  video_downloading: 'waiting for the video download',
  no_phrase_time: 'not timed in the video',
  source_busy: 'in a busy source',
  cloze_needs_choice: 'with cloze words to pick',
}

const cardsLabel = (count: number) => `${count} ${count === 1 ? 'card' : 'cards'}`

export interface MissingPartView {
  part: MissingCardPart
  label: string
  generating: boolean
  /** Почему эту часть не догенерировать; null — догенерируется. */
  reason: string | null
}

/** Чего нет у карточки: у каждой части своё состояние и своя причина. */
export function missingParts(card: CardPreview): MissingPartView[] {
  return card.missing.map(part => {
    const generating = card.generating.includes(part)
    const skip = generating ? undefined : card.cannot_fill.find(s => s.part === part)
    return {
      part,
      generating,
      label: generating ? GENERATING_LABEL[part] : MISSING_LABEL[part],
      reason: skip ? CARD_SKIP_LABEL[skip.reason] : null,
    }
  })
}

/** Подпись секции неполных, по строке на факт: что генерируется и что догенерация пропустит. */
export function fillLines(fill: ExportFill): string[] {
  const generating = fill.generating > 0 ? [`Generating ${cardsLabel(fill.generating)}…`] : []
  const skipped = fill.skipped.map(s => `Can't generate ${cardsLabel(s.cards)} ${SECTION_SKIP_LABEL[s.reason]}`)
  return [...generating, ...skipped]
}
