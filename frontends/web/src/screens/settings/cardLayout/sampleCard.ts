import type { CardPhrase, StoredCandidate } from '@/api/types'
import type { CardBlockContext } from '@/cardLayout'

const PHRASE: CardPhrase = {
  text: 'He glared at me across the table.',
  words: [[0, 2], [3, 9], [10, 12], [13, 15], [16, 22], [23, 26], [27, 32]],
  target: [1],
}
const SOURCE_ID = 0
const AUDIO = 'sample.mp3'

/** Карточка для превью раскладки: в ней заполнено всё, что умеет показать тело карточки. */
export const SAMPLE_CARD = {
  phrase_id: 0,
  lemma: 'glare',
  phrase: PHRASE,
  source_phrase: PHRASE,
  cefr_level: 'C1',
  is_sweet_spot: true,
  is_phrasal_verb: false,
  frequency_band: 'MID',
  usage_distribution: null,
  meaning: {
    meaning: [
      'to look at someone in an angry way, without speaking',
      'He looked at me angrily across the table.',
      'Often followed by **at**: glare at someone.',
    ].join('\n'),
    translation: 'сердито смотреть',
    synonyms: 'scowl, stare, glower',
    examples: 'She **glared** at the referee.\nThe two men **glared** at each other in silence.',
    ipa: '/ɡleər/',
    status: 'done',
    error: null,
    generated_at: null,
  },
  meaning_action: null,
  media: null,
  meaning_image_path: null,
  pronunciation: { us_audio_path: AUDIO, uk_audio_path: AUDIO, status: 'done', error: null, generated_at: null },
  tts: { audio_path: AUDIO, status: 'done', error: null, generated_at: null },
  source: { id: SOURCE_ID, has_video: true, can_polish_phrases: false },
} as StoredCandidate

/** Что может быть у карточки: превью показывает образец, у которого есть только выбранное. */
export type SamplePart = 'meaning' | 'pronunciation' | 'tts' | 'video' | 'picture'

export const SAMPLE_PARTS: { part: SamplePart; label: string }[] = [
  { part: 'meaning', label: 'Meaning' },
  { part: 'pronunciation', label: 'US / UK audio' },
  { part: 'tts', label: 'TTS' },
  { part: 'video', label: 'Video frame' },
  { part: 'picture', label: 'Picture' },
]

export const ALL_SAMPLE_PARTS: ReadonlySet<SamplePart> = new Set(SAMPLE_PARTS.map(({ part }) => part))

const SAMPLE_FRAME_URL = '/sample-frame.svg'
const SAMPLE_PICTURE_URL = '/sample-picture.svg'

/** Превью ничего не делает: кнопки карточки в нём только для вида. */
const SAMPLE_ACTIONS: Omit<CardBlockContext, 'candidate' | 'media'> = {
  playingUrl: null,
  togglePlay: () => {},
  keyAudioUrl: null,
  generating: false,
  generate: () => {},
  useExample: () => {},
  pictureSuggestions: null,
  showCefr: () => {},
}

/** Образец карточки, у которого есть только выбранные части. */
export function sampleContext(parts: ReadonlySet<SamplePart>): CardBlockContext {
  const has = (part: SamplePart) => parts.has(part)
  const candidate: StoredCandidate = {
    ...SAMPLE_CARD,
    meaning: has('meaning') ? SAMPLE_CARD.meaning : null,
    meaning_action: has('meaning') ? null : 'generate',
    pronunciation: has('pronunciation') ? SAMPLE_CARD.pronunciation : null,
    tts: has('tts') ? SAMPLE_CARD.tts : null,
    source: { ...SAMPLE_CARD.source, has_video: has('video') },
  }
  return {
    ...SAMPLE_ACTIONS,
    candidate,
    media: {
      screenshotUrl: has('video') ? SAMPLE_FRAME_URL : null,
      audioUrl: has('video') ? `/media/${SOURCE_ID}/${AUDIO}` : null,
      meaningImageUrl: has('picture') ? SAMPLE_PICTURE_URL : null,
    },
  }
}
