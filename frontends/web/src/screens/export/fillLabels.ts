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

/** Строка под карточкой: чего нет, что генерируется и почему часть не догенерировать. */
export function missingLine(card: CardPreview): string {
  return card.missing.map(part => {
    if (card.generating.includes(part)) return GENERATING_LABEL[part]
    const skip = card.cannot_fill.find(s => s.part === part)
    return skip ? `${MISSING_LABEL[part]} (${CARD_SKIP_LABEL[skip.reason]})` : MISSING_LABEL[part]
  }).join(' · ')
}

/** Подпись секции неполных: что генерируется и что догенерация пропустит. */
export function fillHint(fill: ExportFill): string | null {
  const parts: string[] = []
  if (fill.generating > 0) parts.push(`Generating ${cardsLabel(fill.generating)}…`)
  if (fill.skipped.length > 0) {
    parts.push(`Can't generate: ${fill.skipped.map(s => `${cardsLabel(s.cards)} ${SECTION_SKIP_LABEL[s.reason]}`).join(', ')}`)
  }
  return parts.length > 0 ? parts.join(' ') : null
}
