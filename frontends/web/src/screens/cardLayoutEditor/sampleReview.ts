import type {
  CardButton, CardPhrase, CandidateMeaning, DocumentPosition, Highlight, ImageOption, ReviewHeader, ReviewRow,
  ReviewUpdate, SetScope, StoredCandidate, TextChunk,
} from '@/api/types'
import type { ReviewApi } from '@/screens/review/reviewApi'

/**
 * Образец для редактора раскладки: один источник и карточки в разных состояниях. Экран ревью получает его
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
    usage_distribution: null,
    origin: null,
    cloze: null,
    can_edit_cloze: true,
    source: { id: SOURCE_ID, has_video: true, can_polish_phrases: false },
  }
}

/** Полная карточка, карточка без картинки (видно подобранные), со своими заметками и без значения. */
const CARDS: StoredCandidate[] = [
  card({
    id: 1, lemma: 'glare', phrase: 'He glared at me across the table', target: 'glared', cefr: 'C1', band: 'MID',
    meaning: meaning({
      meaning: 'If you **glare** at someone, you look at them angrily for a long time, usually without saying anything.\n'
        + 'The man sat on the other side of the table and stared at the speaker with an angry, hostile look.',
      translation: 'сердито смотреть, свирепо глядеть',
      synonyms: 'stare angrily, scowl, glower',
      examples: 'The driver **glared** at me when I crossed the street too slowly.\n'
        + 'My sister **glared** at her brother after he broke her phone.\nThe teacher **glared** at the students who were talking.',
      ipa: '/ɡler/',
    }),
    video: true, picture: true, pronunciation: true, tts: true,
  }),
  card({
    id: 2, lemma: 'placate', phrase: 'She tried to placate him with a smile', target: 'placate', cefr: 'C2', band: 'LOW',
    meaning: meaning({
      meaning: 'If you **placate** someone, you do or say something to make them stop feeling angry.\n'
        + 'She smiled at the angry man, hoping that her friendly face would calm him down.',
      translation: 'успокаивать, умиротворять',
      synonyms: 'calm, soothe, pacify',
      examples: 'He bought her flowers to **placate** her after the argument.\n'
        + 'The company lowered its prices to **placate** angry customers.',
      ipa: '/ˈpleɪkeɪt/',
    }),
    video: true, pronunciation: true, tts: true,
  }),
  card({
    id: 3, lemma: 'give in', phrase: 'but he would not give in', target: 'give', cefr: 'B1', band: 'HIGH', phrasal: true,
    meaning: meaning({
      meaning: 'If you **give in**, you finally agree to what someone wants after refusing for a while.\n'
        + 'However much she tried, the man refused to change his mind and let her have her way.\n'
        + '**Give** means to hand something over; **in** here shows that you stop resisting. Learn it as one phrase.',
      translation: 'сдаться, уступить',
      synonyms: 'yield, surrender, back down',
      examples: 'The children kept asking until their parents **gave in**.\nI will not **give in** to their demands.',
      ipa: '/ɡɪv ɪn/',
    }),
    tts: true,
  }),
  card({
    id: 4, lemma: 'concession', phrase: 'nobody wanted to make a concession', target: 'concession', cefr: 'C1', band: 'MID',
    meaning: null, pronunciation: true,
  }),
]

const BY_ID = new Map(CARDS.map(c => [c.phrase_id, c]))

const ROWS: ReviewRow[] = [
  ...CARDS.map((c, i) => ({ index: i, kind: 'card' as const, phrase_id: c.phrase_id, position: i + 1, section: null, count: null, open: null })),
  { index: CARDS.length, kind: 'section', phrase_id: null, position: null, section: 'extra', count: 3, open: false },
  { index: CARDS.length + 1, kind: 'section', phrase_id: null, position: null, section: 'probably_known', count: 2, open: false },
]

const HEADER: ReviewHeader = {
  scope: SAMPLE_SCOPE,
  title: 'Sample',
  status: 'done',
  progress: { decided: 0, total: CARDS.length },
  learn_count: 0,
  busy: false,
}

const HIGHLIGHTS: Highlight[] = CARDS.map(c => ({
  phrase_id: c.phrase_id,
  word_id: c.word_id,
  position: positionOf(c.source_phrase.text.slice(...c.source_phrase.words[c.source_phrase.target[0]])),
  cefr_level: c.cefr_level,
  is_phrasal_verb: c.is_phrasal_verb,
  is_done: false,
}))

const CHUNK: TextChunk = {
  source_id: SOURCE_ID,
  first_block: BLOCK,
  end_block: BLOCK + 1,
  block_count: 1,
  start_offset: 0,
  end_offset: TEXT.length,
  text_length: TEXT.length,
  blocks: [{ type: 'paragraph', lines: [{ text: TEXT }], level: null, mode: 'flow', ordered: null, depth: null, number: null }],
  highlights: HIGHLIGHTS,
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

const everything = (focus: number | null) => update(focus, {
  layout: { version: 1, total_rows: ROWS.length, total_cards: CARDS.length, replace: true, rows: ROWS },
  cards: CARDS,
})

const unchanged = () => Promise.reject(new Error('The sample card does not change'))

/** Ревью образца: читает всё из образца, ничего не меняет. */
export const SAMPLE_REVIEW_API: ReviewApi = {
  openReview: async request => everything(request.requested_id ?? CARDS[0].phrase_id),
  reviewRows: async ctx => everything(ctx.current),
  reviewAround: async (_ctx, phraseId) => everything(BY_ID.has(phraseId) ? phraseId : CARDS[0].phrase_id),
  reviewChanges: async ctx => update(ctx.current),
  setReviewSection: async ctx => update(ctx.current),
  reviewContents: async () => ({ version: 1, documents: [{ source_id: SOURCE_ID, title: HEADER.title, size_hint: TEXT.length }] }),
  reviewText: async ctx => update(ctx.current, { text: CHUNK }),
  getReviewGeneration: async () => ({ kinds: [], in_progress: false }),
  suggestTargetImages: async wordId => ({ status: 'ready', query: BY_ID.get(wordId)?.lemma ?? '', options: SAMPLE_PICTURES }),
  searchTargetImages: async () => ({ query: '', options: SAMPLE_PICTURES }),
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
