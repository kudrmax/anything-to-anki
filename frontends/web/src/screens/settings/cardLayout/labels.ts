import type { BlockAlign, BlockSize, BlockTone, BlockVAlign, CardElement, ColumnWidth } from '@/api/types'

export const ELEMENT_LABEL: Record<CardElement, string> = {
  target: 'Target word',
  translation: 'Translation',
  context: 'Meaning in context',
  definition: 'Definition',
  notes: 'More meaning',
  synonyms: 'Synonyms',
  examples: 'Examples',
  transcription: 'Transcription',
  pronunciation: 'US / UK audio',
  tts: 'TTS audio',
  word_facts: 'Level and frequency',
  video_frame: 'Video frame',
  picture: 'Picture',
  meaning_status: 'Generate meaning',
}

/** Что элемент показывает: подпись под названием в панели блока. */
export const ELEMENT_HINT: Record<CardElement, string> = {
  target: 'The word, phrasal verb or collocation you learn.',
  translation: 'Translation of the target.',
  context: 'Second line of the meaning: what the target means in this phrase.',
  definition: 'First line of the meaning: the dictionary definition.',
  notes: 'Anything the meaning adds after its first two lines. Most cards have none.',
  synonyms: 'Synonyms of the target.',
  examples: 'Example sentences. Hover one to use it as the phrase.',
  transcription: 'IPA transcription.',
  pronunciation: 'Buttons that play US and UK pronunciation.',
  tts: 'Button that plays the phrase read by text-to-speech.',
  word_facts: 'CEFR level, phrasal verb mark, frequency and register.',
  video_frame: 'Frame and audio clip from the video.',
  picture: 'Picture of the target, or picture suggestions.',
  meaning_status: 'Progress, Generate or Retry while the card has no meaning yet.',
}

export const SIZE_OPTIONS: { value: BlockSize; label: string }[] = [
  { value: 'xs', label: 'XS' },
  { value: 's', label: 'S' },
  { value: 'm', label: 'M' },
  { value: 'l', label: 'L' },
  { value: 'xl', label: 'XL' },
]

export const TONE_OPTIONS: { value: BlockTone; label: string }[] = [
  { value: 'primary', label: 'Main' },
  { value: 'secondary', label: 'Grey' },
  { value: 'muted', label: 'Light grey' },
  { value: 'accent', label: 'Accent' },
]

export const ALIGN_OPTIONS: { value: BlockAlign; label: string }[] = [
  { value: 'start', label: 'Left' },
  { value: 'end', label: 'Right' },
]

export const VALIGN_OPTIONS: { value: BlockVAlign; label: string }[] = [
  { value: 'top', label: 'Top' },
  { value: 'middle', label: 'Middle' },
  { value: 'bottom', label: 'Bottom' },
]

export const WIDTH_OPTIONS: { value: ColumnWidth; label: string }[] = [
  { value: 'narrow', label: 'Narrow' },
  { value: 'normal', label: 'Normal' },
  { value: 'wide', label: 'Wide' },
]
