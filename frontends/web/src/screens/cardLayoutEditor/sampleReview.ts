import type {
  CardButton, CardPhrase, CandidateMeaning, DocumentPosition, Highlight, ImageOption, ReviewHeader, ReviewRow,
  ReviewUpdate, SetScope, StoredCandidate, TextChunk,
} from '@/api/types'
import type { ReviewApi } from '@/screens/review/reviewApi'
import type { SamplePart } from './sampleParts'

/**
 * Образец для редактора раскладки: один источник и карточка, у которой есть только выбранное. Экран ревью получает его
 * через тот же источник данных, что и ответы бэкенда, и рисует как обычно.
 */

const SOURCE_ID = 0
export const SAMPLE_SCOPE: SetScope = `source-${SOURCE_ID}`
const REVIEW_ID = 'layout-sample'
const BLOCK = 0
const TEXT =
  'He glared at me across the table, furious that I had taken his seat. She tried to placate him with a smile, '
  + 'but he would not give in. The negotiations dragged on for hours, and nobody wanted to make a concession. '
  + 'Eventually the chairman lost his temper and stormed out of the room.'

/** Медиа образца лежат в приложении, а не у источника. */
const SAMPLE_MEDIA_DIR = '/layout-sample'
const SAMPLE_PICTURES: ImageOption[] = [1, 2, 3, 4, 5].map(n => ({ url: `${SAMPLE_MEDIA_DIR}/suggestions/${n}.svg`, provider: 'bing' }))

const WORD = /[A-Za-z']+/g

function phraseOf(text: string, target: string): CardPhrase {
  const words = [...text.matchAll(WORD)].map(m => [m.index, m.index + m[0].length] as [number, number])
  const targetWords = target.split(' ')
  const first = words.findIndex(([start, end]) => text.slice(start, end).toLowerCase().startsWith(targetWords[0]))
  return { text, words, target: targetWords.map((_, i) => first + i) }
}

function positionOf(phrase: string): DocumentPosition {
  const start = TEXT.indexOf(phrase)
  return { block: BLOCK, start_line: 0, start_char: start, end_line: 0, end_char: start + phrase.length }
}

/** Кнопки новой карточки, как их отдаёт бэкенд. */
const BUTTONS: CardButton[] = [
  { button: 'learn', command: 'decide', pressed: false, refused: null, closes: 'lemma' },
  { button: 'cloze', command: 'edit_cloze', pressed: false, refused: null, closes: 'lemma' },
  { button: 'known', command: 'decide', pressed: false, refused: null, closes: 'lemma' },
  { button: 'skip', command: 'decide', pressed: false, refused: null, closes: 'card' },
]

const DONE_AT = '2026-10-28T00:00:00Z'

function meaning(fields: Omit<CandidateMeaning, 'status' | 'error' | 'generated_at'>): CandidateMeaning {
  return { ...fields, status: 'done', error: null, generated_at: DONE_AT }
}

interface SampleCard {
  id: number
  lemma: string
  /** Фраза карточки — кусок текста источника. */
  phrase: string
  target: string
  cefr: string
  band: string
  phrasal?: boolean
  meaning: CandidateMeaning | null
  video?: boolean
  picture?: boolean
  pronunciation?: boolean
  tts?: boolean
}

const audio = (id: number, kind: string) => `${id}_${kind}.mp3`

function card(sample: SampleCard): StoredCandidate {
  const phrase = phraseOf(sample.phrase, sample.target)
  return {
    phrase_id: sample.id,
    word_id: sample.id,
    lemma: sample.lemma,
    pos: 'VERB',
    cefr_level: sample.cefr,
    zipf_frequency: 3,
    is_sweet_spot: false,
    reported: false,
    phrase,
    source_phrase: phrase,
    polished_phrase: null,
    polish_reverted: false,
    polish_status: null,
    section: 'ready',
    occurrences: 1,
    choice: 'none',
    shown: { status: 'new', skipped: false, where: 'nowhere', tone: 'open' },
    state: { buttons: BUTTONS },
    is_done: false,
    is_phrasal_verb: sample.phrasal ?? false,
    phrase_position: positionOf(sample.phrase),
    meaning: sample.meaning,
    meaning_action: sample.meaning ? null : 'generate',
    media: sample.video
      ? { screenshot_path: 'frame.svg', audio_path: audio(sample.id, 'clip'), start_ms: 0, end_ms: 2000, status: 'done', error: null, generated_at: DONE_AT }
      : null,
    meaning_image_path: sample.picture ? 'picture.svg' : null,
    pronunciation: sample.pronunciation
      ? { us_audio_path: audio(sample.id, 'us'), uk_audio_path: audio(sample.id, 'uk'), status: 'done', error: null, generated_at: DONE_AT }
      : null,
    tts: sample.tts ? { audio_path: audio(sample.id, 'tts'), status: 'done', error: null, generated_at: DONE_AT } : null,
    audio_path: sample.video ? audio(sample.id, 'clip') : sample.tts ? audio(sample.id, 'tts') : null,
    frequency_band: sample.band,
    usage_group: null,
    origin: null,
    cloze: null,
    can_edit_cloze: true,
    source: { id: SOURCE_ID, has_video: true, can_polish_phrases: false },
  }
}

const SAMPLE_PHRASE = 'He glared at me across the table'
const SAMPLE_TARGET = 'glared'

/** Карточка образца с тем, что выбрано; значение — в три абзаца, как бывает на настоящих карточках. */
function sampleCard(parts: ReadonlySet<SamplePart>): StoredCandidate {
  const has = (part: SamplePart) => parts.has(part)
  return card({
    id: 1, lemma: 'glare', phrase: SAMPLE_PHRASE, target: SAMPLE_TARGET, cefr: 'C1', band: 'MID',
    meaning: has('meaning')
      ? meaning({
          meaning: 'If you **glare** at someone, you look at them angrily for a long time, usually without saying anything, '
            + 'because you are annoyed or upset with them.\n'
            + 'The man sat on the other side of the table and stared at the speaker with an angry, hostile look instead of talking.\n'
            + 'Usually followed by **at**: you glare at a person. Compare **stare**, which does not have to be angry.',
          translation: 'сердито смотреть, свирепо глядеть',
          synonyms: 'stare angrily, scowl, glower, frown',
          examples: 'She **glared** at the referee after he gave the other team a penalty in the last minute.\n'
            + 'The two men **glared** at each other in silence across the crowded room.\n'
            + 'My brother **glared** at me when I told our parents about his bad grades.',
          ipa: '/ɡler/',
        })
      : null,
    video: has('video'), picture: has('picture'), pronunciation: has('pronunciation'), tts: has('tts'),
  })
}

const SECTION_ROWS: ReviewRow[] = [
  { index: 1, kind: 'section', phrase_id: null, position: null, section: 'extra', count: 3, open: false },
  { index: 2, kind: 'section', phrase_id: null, position: null, section: 'probably_known', count: 2, open: false },
]

const HEADER: ReviewHeader = {
  scope: SAMPLE_SCOPE,
  title: 'Sample',
  status: 'done',
  progress: { decided: 0, total: 1 },
  learn_count: 0,
  busy: false,
}

function chunkOf(sample: StoredCandidate): TextChunk {
  const highlight: Highlight = {
    phrase_id: sample.phrase_id,
    word_id: sample.word_id,
    position: positionOf(SAMPLE_TARGET),
    cefr_level: sample.cefr_level,
    is_phrasal_verb: sample.is_phrasal_verb,
    is_done: false,
  }
  return {
    source_id: SOURCE_ID,
    first_block: BLOCK,
    end_block: BLOCK + 1,
    block_count: 1,
    start_offset: 0,
    end_offset: TEXT.length,
    text_length: TEXT.length,
    blocks: [{ type: 'paragraph', lines: [{ text: TEXT }], level: null, mode: 'flow', ordered: null, depth: null, number: null }],
    highlights: [highlight],
  }
}

function update(focus: number | null, parts: Partial<ReviewUpdate> = {}): ReviewUpdate {
  return {
    review_id: REVIEW_ID,
    revision: 1,
    header: HEADER,
    layout: null,
    cards: [],
    removed: [],
    done: {},
    focus_id: focus,
    text: null,
    highlights: [],
    contents_version: 1,
    undo: null,
    ...parts,
  }
}

const unchanged = () => Promise.reject(new Error('The sample card does not change'))

/** Ревью образца: одна карточка с выбранными частями; читает всё из образца, ничего не меняет. */
export function sampleReviewApi(parts: ReadonlySet<SamplePart>): ReviewApi {
  const sample = sampleCard(parts)
  const rows: ReviewRow[] = [
    { index: 0, kind: 'card', phrase_id: sample.phrase_id, position: 1, section: null, count: null, open: null },
    ...SECTION_ROWS,
  ]
  const everything = () => update(sample.phrase_id, {
    layout: { version: 1, total_rows: rows.length, total_cards: 1, replace: true, rows },
    cards: [sample],
  })
  return {
    openReview: async () => everything(),
    reviewRows: async () => everything(),
    reviewAround: async () => everything(),
    reviewChanges: async () => update(sample.phrase_id),
    setReviewSection: async () => update(sample.phrase_id),
    reviewContents: async () => ({ version: 1, documents: [{ source_id: SOURCE_ID, title: HEADER.title, size_hint: TEXT.length }] }),
    reviewText: async () => update(sample.phrase_id, { text: chunkOf(sample) }),
    getReviewGeneration: async () => ({ kinds: [], in_progress: false }),
    suggestTargetImages: async () => ({ status: 'ready', query: sample.lemma, options: SAMPLE_PICTURES }),
    searchTargetImages: async () => ({ query: sample.lemma, options: SAMPLE_PICTURES }),
    getReportReasons: async () => [],
    mediaUrl: (_sourceId, path) => (path ? `${SAMPLE_MEDIA_DIR}/${path}` : null),
    runReviewGeneration: unchanged,
    cancelReviewGeneration: unchanged,
    downloadReviewVideos: unchanged,
    previewCloze: unchanged,
    saveCloze: unchanged,
    decidePhrase: unchanged,
    undoDecision: unchanged,
    generateMeaning: unchanged,
    regeneratePhraseMedia: unchanged,
    generatePhraseTTS: unchanged,
    replaceWithExample: unchanged,
    replaceWithTarget: unchanged,
    applyTargetImage: unchanged,
    pasteTargetImage: unchanged,
    polishPhraseAgain: unchanged,
    setPolishReverted: unchanged,
    editPhrase: unchanged,
    setPhraseBoundary: unchanged,
    addManualCandidate: unchanged,
    reportCandidate: unchanged,
  }
}
