/** Что может быть у карточки образца: редактор показывает карточку только с выбранным. */
export type SamplePart = 'meaning' | 'pronunciation' | 'tts' | 'video' | 'picture' | 'picture_choice'

export const SAMPLE_PARTS: { part: SamplePart; label: string }[] = [
  { part: 'meaning', label: 'Meaning' },
  { part: 'pronunciation', label: 'US / UK audio' },
  { part: 'tts', label: 'TTS' },
  { part: 'video', label: 'Video frame' },
  { part: 'picture', label: 'Picture' },
  { part: 'picture_choice', label: 'Picture choice' },
]

/** Картинка либо выбрана, либо из подобранных ещё выбирают: у карточки не бывает обоих сразу. */
const EXCLUSIVE_PARTS: Partial<Record<SamplePart, SamplePart>> = { picture: 'picture_choice', picture_choice: 'picture' }

export const DEFAULT_SAMPLE_PARTS: ReadonlySet<SamplePart> = new Set(
  SAMPLE_PARTS.map(({ part }) => part).filter(part => part !== 'picture_choice'),
)

/** Включает или выключает часть образца; включённая часть выключает ту, что с ней не бывает. */
export function toggleSamplePart(parts: ReadonlySet<SamplePart>, part: SamplePart): ReadonlySet<SamplePart> {
  const next = new Set(parts)
  if (next.delete(part)) return next
  next.add(part)
  const exclusive = EXCLUSIVE_PARTS[part]
  if (exclusive) next.delete(exclusive)
  return next
}

/** Ключ набора частей: другой набор — другой образец, экран ревью открывается на нём заново. */
export const samplePartsKey = (parts: ReadonlySet<SamplePart>): string =>
  SAMPLE_PARTS.map(({ part }) => (parts.has(part) ? part : '')).join('|')
