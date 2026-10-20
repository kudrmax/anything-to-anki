export type SourceStatus =
  | 'new'
  | 'processing'
  | 'done'
  | 'error'
  | 'partially_reviewed'
  | 'reviewed'

/** Что это за контент: текст, книга, субтитры, песня. У Topic и Saved phrases вида нет. */
export type SourceKind = 'text' | 'book' | 'subtitles' | 'song'
export type SourceRole = 'content' | 'topic' | 'saved_phrases'
export type SourceFormat = 'plain' | 'markdown' | 'html' | 'epub' | 'srt' | 'video_file' | 'youtube'

export type ProcessingStage = 'analyzing_text' | 'collecting_phrases'

export type CandidateSortOrder = 'relevance' | 'chronological' | 'key_words'

export type Scope = 'all' | 'unsorted' | number
/** Набор источников на ревью и экспорте: область или один источник (`source-<id>`). */
export type SetScope = Scope | `source-${number}`
export type SourceStage = 'in_progress' | 'preparing' | 'ready' | 'reviewed'

/** Один на всё приложение выбор порядка источников: группировка и сортировка внутри групп. */
export type SourceGrouping = 'stage' | 'none'
export type SourceSort = 'added' | 'name' | 'last_studied'
export type SourceSortDirection = 'forward' | 'reverse'

/** Решённые карточки среди Ready: одни и те же числа у источника, его ревью и коллекции. */
export interface Progress {
  decided: number
  total: number
}

export interface ScopeCounts extends SetOffer {
  total: number
  reviewed: number
  pending: number
  progress: Progress
  /** Область как один набор на ревью: статус, есть ли что обработать, можно ли открыть ревью, доля и подпись — как у источника. */
  status: SourceStatus
  can_process: boolean
  can_review: boolean
  review_fraction: number
  progress_caption: string
}

export interface CollectionNode {
  id: number
  name: string
  parent_id: number | null
  counts: ScopeCounts
  /** Глубина узла: верхний уровень — 1. */
  depth: number
  /** Может получить новую подколлекцию. */
  accepts_collections: boolean
  /** Все допустимые новые родители, включая текущего; null — верхний уровень. */
  move_targets: (number | null)[]
  children: CollectionNode[]
}

export interface CollectionTree {
  all: ScopeCounts
  unsorted: ScopeCounts
  max_depth: number
  collections: CollectionNode[]
}

export interface Collection {
  id: number
  name: string
  parent_id: number | null
  position: number
}

export interface RenamedCollection {
  id: number
  name: string
  previous_name: string
}

export interface MovedCollection {
  id: number
  previous_parent_id: number | null
  previous_position: number
}

export interface DeletedCollection {
  id: number
  name: string
  evicted_source_count: number
}

export interface SourcePlacement {
  source_id: number
  collection_id: number | null
}

export type SetOperation = 'update' | 'recut' | 'refresh'

/** Rebuild раскладывает карточки по знанию; с новыми фразами — ещё и режет фразы заново. */
export type RebuildMode = 'update' | 'recut'

/** Что предлагает меню «…» источника или набора: одни поля у обоих; решает backend. */
export interface SetOffer {
  /** Как привести набор в актуальное состояние, в порядке меню. */
  available_operations: SetOperation[]
  /** false — всё, что можно обновить, занято другой операцией: пункт виден, но недоступен. */
  can_start_operation: boolean
  /** Почему операция сейчас недоступна. */
  operation_hint: string | null
  can_export: boolean
}

export interface SourceSummary extends SetOffer {
  id: number
  title: string
  status: SourceStatus
  kind: SourceKind | null
  role: SourceRole
  /** Субтитры видеофайла или YouTube: кадры и аудио на карточках. */
  has_video: boolean
  source_url: string | null
  video_downloaded: boolean
  created_at: string
  candidate_count: number
  learn_count: number
  progress: Progress
  processing_stage: ProcessingStage | null
  collection_id: number | null
  collection_path: string[]
  stage: SourceStage
  /** Тема ещё ждёт AI-шага: запрос не превращён в target'ы. */
  awaiting_generation: boolean
  generation_status: GenerationStatus | null
  generation_error: string | null
  /** Операция, которой занят источник; другую сейчас не начать. */
  busy_with: SourceOperationKind | null
  /** Что источник позволяет сейчас; решает backend. */
  can_process: boolean
  can_review: boolean
  can_delete: boolean
  /** Доля разобранного, 0..1; разобранный источник — 1. */
  review_fraction: number
  /** Подпись под шкалой: чем занят источник или где его разбор. */
  progress_caption: string
}

export type SourceOperationKind = 'process' | 'update' | 'recut' | 'preview' | 'refresh'

export type GenerationStatus = 'queued' | 'running' | 'failed'

export type PhraseOriginKind = 'source' | 'generated'

export interface PhraseOrigin {
  kind: PhraseOriginKind
  source_title: string | null
}

export type EnrichmentStatus = 'queued' | 'running' | 'done' | 'failed' | 'idle'

export interface CandidateMeaning {
  meaning: string | null
  translation: string | null
  synonyms: string | null
  examples: string | null
  ipa: string | null
  status: EnrichmentStatus
  error: string | null
  generated_at: string | null
}

export interface CandidateMedia {
  screenshot_path: string | null
  audio_path: string | null
  start_ms: number | null
  end_ms: number | null
  status: EnrichmentStatus
  error: string | null
  generated_at: string | null
}

export interface CandidatePronunciation {
  us_audio_path: string | null
  uk_audio_path: string | null
  status: EnrichmentStatus
  error: string | null
  generated_at: string | null
}

export interface CandidateTTS {
  audio_path: string | null
  status: EnrichmentStatus
  error: string | null
  generated_at: string | null
}

export interface SourceVote {
  source_name: string
  level: string | null
  distribution: Record<string, number> | null
}

export interface CEFRBreakdown {
  decision_method: 'priority' | 'voting'
  priority_votes: SourceVote[]
  votes: SourceVote[]
}

export type ImageProvider = 'wiktionary' | 'bing' | 'yandex'

/** Картинка, которую можно поставить на карточку вместо текущей. */
export interface ImageOption {
  url: string
  provider: ImageProvider
}

/** Найденные картинки и запрос, по которому их искали (по умолчанию — сам target). */
export interface ImageSearchResult {
  query: string
  options: ImageOption[]
}

export type ClozeHintKind = 'none' | 'translation' | 'synonyms' | 'first_letter' | 'custom'

/** Подсказка по умолчанию: своя пишется только под конкретную карточку. */
export type ClozeDefaultHint = Exclude<ClozeHintKind, 'custom'>

/** Какие слова фразы скрыты на cloze-карточке и какая подсказка к пропуску. */
export interface CandidateCloze {
  hidden_word_indices: number[]
  hint_kind: ClozeHintKind
  custom_hint: string | null
}

export type ClozeDraft = CandidateCloze

/** Сохранение разметки: `phrase` — фраза, в которой выбраны слова (из превью). */
export interface SaveClozeRequest extends ClozeDraft {
  phrase: string
}

export interface ClozeWord {
  index: number
  text: string
  is_target: boolean
}

/** Кусок лицевой стороны: текст фразы или пропуск с подсказкой, как его покажет Anki. */
export interface ClozeFrontPart {
  text: string
  is_gap: boolean
}

/** Как будет выглядеть cloze-карточка: слова фразы, лицевая сторона и доступные подсказки. */
export interface ClozePreview {
  /** Фраза карточки, к которой относятся слова и индексы. */
  phrase: string
  words: ClozeWord[]
  hidden_word_indices: number[]
  hint_kind: ClozeHintKind
  custom_hint: string | null
  front: ClozeFrontPart[]
  available_hints: ClozeHintKind[]
  /** Разметку можно сохранить: те же правила, что у сохранения. */
  can_save: boolean
}

/** Фраза карточки: текст как есть, слова — символы [start, end), target — номера слов. */
export interface CardPhrase {
  text: string
  words: [number, number][]
  target: number[]
}

/** Where a card stands in review: only the target is new, more words are new, probably known, or done (reviewed). */
export type CandidateSection = 'ready' | 'extra' | 'probably_known' | 'reviewed'

export type DecisionButton = 'learn' | 'cloze' | 'known' | 'skip'

/** Что делает нажатие: decide шлёт кнопку, edit_cloze открывает разметку cloze — её Save и есть нажатие. */
export type ButtonCommand = 'decide' | 'edit_cloze'

/** Почему кнопка не работает: слово решено на другой фразе или в другом источнике. */
export type Refusal = 'not_decision_card' | 'decided_elsewhere'

/** Кнопка решения: что делает нажатие (null — кнопка неактивна, refused — почему), нажата ли она; решает backend. */
export interface CardButton {
  button: DecisionButton
  command: ButtonCommand | null
  pressed: boolean
  refused: Refusal | null
}

/** Выбор пользователя на карточке. */
export type CardChoice = 'none' | 'learn' | 'cloze' | 'known' | 'skip'

/** Что карточка показывает о слове: статус, пропущена ли фраза и откуда статус — здесь, другая фраза, другой источник. */
export interface Shown {
  status: ShownStatus
  skipped: boolean
  where: ShownWhere
  /** Как карточка читается с одного взгляда; решение слова важнее Skip — решает backend. */
  tone: ShownTone
}

export type ShownStatus = 'new' | 'learn' | 'learning' | 'known'
export type ShownWhere = 'here' | 'other_card' | 'other_source' | 'nowhere'
export type ShownTone = 'open' | 'learning' | 'settled'

/** Что делает каждая кнопка карточки; считает backend. */
export interface CardState {
  /** Learn, Cloze, Known, Skip — в этом порядке. */
  buttons: CardButton[]
}

/** Карточка — показанная фраза слова; ключ карточки — phrase_id. */
export interface StoredCandidate {
  phrase_id: number
  word_id: number
  lemma: string
  pos: string
  cefr_level: string | null
  zipf_frequency: number
  is_sweet_spot: boolean
  /** На карточку уже жаловались. */
  reported: boolean
  /** Фраза карточки: переписанная (AI или вручную), если её не откатили. */
  phrase: CardPhrase
  /** Фраза как в источнике. */
  source_phrase: CardPhrase
  /** Переписанная фраза — только если она отличается от фразы источника. */
  polished_phrase: CardPhrase | null
  polish_reverted: boolean
  /** AI ещё работает над фразой. */
  polish_status: EnrichmentStatus | null
  section: CandidateSection | null
  occurrences: number
  choice: CardChoice
  shown: Shown
  state: CardState
  /** Карточка разобрана: слово решено, фраза пропущена или слово разобрано в другом источнике. */
  is_done: boolean
  is_phrasal_verb: boolean
  /** Где фраза источника стоит в документе; у примера, темы и сохранённой фразы её нет. */
  phrase_position: DocumentPosition | null
  meaning: CandidateMeaning | null
  /** Что предложить, пока текста значения нет: сгенерировать или повторить; решает backend. */
  meaning_action: 'generate' | 'retry' | null
  media: CandidateMedia | null
  /** Картинка-значение target'а: идёт на оборот карточки, кадр из видео — в media. */
  meaning_image_path: string | null
  pronunciation: CandidatePronunciation | null
  tts: CandidateTTS | null
  /** Аудио, которое карточка играет сама и по клавише; выбирает backend. */
  audio_path: string | null
  cefr_breakdown?: CEFRBreakdown | null
  frequency_band: string | null
  usage_distribution: Record<string, number> | null
  origin: PhraseOrigin | null
  /** Разметка cloze; есть только у фраз на изучение. */
  cloze: CandidateCloze | null
  /** Скрытые слова cloze можно поменять: cloze ещё не в Anki. */
  can_edit_cloze: boolean
  /** Источник карточки: от него её медиа, видео и занятость. */
  source: CardSource
}

export interface CardSource {
  id: number
  has_video: boolean
  can_polish_phrases: boolean
}

/** Ревью набора источников: один источник, коллекция или все. Статус, прогресс и занятость — по набору. */
export interface ReviewDetail {
  /** Токен набора, как его принимает параметр scope. */
  scope: string
  title: string
  status: SourceStatus
  progress: Progress
  /** Слов на изучение (не карточек). */
  learn_count: number
  candidates: StoredCandidate[]
  /** How many candidates to show before "Show more"; null — show all. */
  initially_shown_candidates: number | null
  /** Какой-то источник набора занят операцией: его карточки ждут её. */
  busy: boolean
}

export interface AnkiStatus {
  available: boolean
  version: number | null
  /** Свои note type пользователя, которые потеряют часть карточек; экспорт в них запрещён. */
  note_type_problems: NoteTypeCheck[]
}

export interface CardPreview {
  candidate_id: number
  /** Карточка списка ревью, откуда пришла заметка: фраза решения. */
  phrase_id: number
  lemma: string
  sentence: string
  meaning: string | null
  translation: string | null
  synonyms: string | null
  examples: string | null
  ipa: string | null
  screenshot_url: string | null
  audio_url: string | null
  pronunciation_us_url: string | null
  pronunciation_uk_url: string | null
  tts_audio_url: string | null
  /** Обязательные части, которых у карточки нет. */
  missing: MissingCardPart[]
  /** Карточка уйдёт в Anki как cloze; в sentence скрытые слова выделены <b>. */
  is_cloze: boolean
}

export type MissingCardPart = 'meaning' | 'audio' | 'cloze'

export type ExportGroup = 'ready' | 'incomplete'

export interface SourceGroup {
  /** null, когда источники не группируются: один список без заголовка. */
  stage: SourceStage | null
  sources: SourceSummary[]
}

export interface SourceBoard {
  title: string
  groups: SourceGroup[]
}

export interface ExportSection {
  source_id: number
  source_title: string
  cards: CardPreview[]
}

export interface GlobalExport {
  title: string | null
  ready: ExportSection[]
  incomplete: ExportSection[]
  exported_count: number
}

export interface SyncResult {
  total: number
  added: number
  skipped: number
  errors: number
  skipped_lemmas: string[]
  error_lemmas: string[]
}

/** Слово в Anki и день, когда оно станет Known. */
export interface InAnkiWord {
  lemma: string
  known_on: string
}

/** Слова «учу», только для просмотра: заметки в Anki и Learn, ещё не экспортированные. */
export interface LearningWords {
  in_anki: InAnkiWord[]
  awaiting_export: string[]
}

export interface Settings {
  cefr_level: string
  frequent_word_threshold: string
  anki_deck_name: string
  ai_provider: string
  ai_model: string
  anki_note_type: string
  anki_cloze_note_type: string
  anki_field_sentence: string
  anki_field_target_word: string
  anki_field_meaning: string
  anki_field_ipa: string
  anki_field_image: string
  anki_field_meaning_image: string
  anki_field_audio: string
  anki_field_translation: string
  anki_field_synonyms: string
  anki_field_examples: string
  anki_field_audio_target_us: string
  anki_field_audio_target_uk: string
  usage_group_order: string[]
  tts_enabled_voices: string[]
  tts_speed: number
  anki_field_audio_tts: string
  /** Сколько картинок берётся у каждого источника для одного target'а. */
  images_per_source: number
  cloze_default_hint: ClozeDefaultHint
  /** Как называется источник из главы книги, например «{{book_name}} ch{{n}}». */
  naming_rule: string
  source_grouping: SourceGrouping
  source_sort: SourceSort
  source_sort_direction: SourceSortDirection
}

export interface FrequentWordThresholdOption {
  value: string
  /** The threshold itself; for Auto — its current value calibrated on your marks. */
  zipf: number | null
  /** Words that go down to the bottom of the list at this threshold. */
  examples: string[]
}

/** A quick reason to report a card; picks_words — choosing it lets the user pick the words they don't know. */
export interface ReportReason {
  label: string
  picks_words: boolean
}

export interface UnknownWord {
  id: number
  lemma: string
  created_at: string
}

/** Слово из списка Known (есть id) или Known по 30 дням в Anki (by_timer, без id); удаляется по removal_key. */
export interface KnownWord {
  id: number | null
  lemma: string
  pos: string | null
  created_at: string
  removal_key: string
  by_timer: boolean
}

export interface Stats {
  learn_count: number
  export_pending_count: number
  queue_active_count: number
  candidate_count: number
  known_word_count: number
}

export type NoteTypeKind = 'recognition' | 'cloze'

export interface NoteTypeCheck {
  kind: NoteTypeKind
  note_type: string
  exists: boolean
  missing_fields: string[]
  /** Что сделает note type готовым: создать его или добавить недостающие поля; null — готов. */
  fix: 'create' | 'add_fields' | null
}

export interface GenerateMeaningResult {
  candidate_id: number
  meaning: string
  translation: string
  synonyms: string
  examples: string
  ipa: string | null
  tokens_used: number
}

export type GenerationKind = 'polish' | 'meaning' | 'media' | 'pronunciation' | 'tts'

/** missing — cards nothing was made for yet; ready_missing — the missing ones in Ready; failed — cards whose last attempt failed; all — every card, replacing results. */
export type GenerationScope = 'missing' | 'ready_missing' | 'failed' | 'all'

export type GenerationBlocker = 'video_not_downloaded' | 'video_downloading'

/** done + running + failed + missing === total; ready_missing is the part of missing in Ready */
export interface GenerationKindStatus {
  kind: GenerationKind
  total: number
  done: number
  running: number
  failed: number
  missing: number
  ready_missing: number
  blocked_by: GenerationBlocker | null
  /** Источники набора, которым этот вид ждёт видео, а оно не скачано и не скачивается. */
  videos_to_download: number
}

/** Фоновая генерация по карточкам источника. */
export interface GenerationOverview {
  kinds: GenerationKindStatus[]
  in_progress: boolean
}

/** Что меняет Update или Re-cut — числа для человека; считает backend. */
export interface RebuildCounts {
  words_added: number
  words_removed: number
  /** Удалённые карточки, для которых что-то было сделано. */
  cards_lost_generation: number
  /** Карточки, переехавшие на фразу без генерации. */
  cards_moved: number
  /** Фразы, нарезанные заново. */
  cards_recut: number
  /** Из них потерявшие Polish, озвучку или видео. */
  cards_recut_lost_text_generation: number
  /** Карточки, попавшие в ready или ушедшие из него. */
  cards_became_ready: number
  cards_left_ready: number
  nothing_to_update: boolean
}

/** Как прошли источники набора: занятые пропущены, упавшие посчитаны; у одного источника обоих нет. */
export interface SetOutcome {
  skipped: number
  failed: number
}

export interface RebuildPreview extends SetOutcome {
  mode: RebuildMode
  counts: RebuildCounts
}

export interface RebuildSummary extends SetOutcome {
  mode: RebuildMode
  counts: RebuildCounts
}

export interface TopicRefreshSummary extends SetOutcome {
  words_added: number
  phrases_added: number
}

/** Долгая операция над набором источников (Rebuild, его превью, Refresh тем), запущенная в фоне. */
export interface SourceOperation {
  operation_id: number
  kind: SourceOperationKind
  state: 'running' | 'done' | 'error'
  /** Что сказать, пока операция идёт; пишет backend. */
  caption: string
  preview: RebuildPreview | null
  summary: RebuildSummary | null
  refresh: TopicRefreshSummary | null
  error: string | null
}

/** Кусок одного блока документа источника; символы — code points, конец не включается. */
export interface DocumentPosition {
  block: number
  start_line: number
  start_char: number
  end_line: number
  end_char: number
}

/** Выделение на экране источника; может задеть несколько блоков — backend это отклонит. */
export interface DocumentSelection {
  start_block: number
  start_line: number
  start_char: number
  end_block: number
  end_line: number
  end_char: number
}

export interface DocumentLine {
  text: string
}

export interface DocumentBlock {
  type: 'heading' | 'paragraph' | 'list_item'
  lines: DocumentLine[]
  level: number | null
  /** flow — предложение продолжается со строки на строку; lines — каждая строка сама по себе. */
  mode: 'flow' | 'lines' | null
  ordered: boolean | null
  depth: number | null
}

export interface Highlight {
  phrase_id: number
  word_id: number
  position: DocumentPosition
  cefr_level: string | null
  is_phrasal_verb: boolean
}

export interface SourceDocument {
  source_id: number
  title: string
  blocks: DocumentBlock[]
  /** Target'ы, которые не пересекаются, в порядке чтения. */
  highlights: Highlight[]
}

export interface DetailItem {
  text: string
  note: string | null
}

export interface QuestionOption {
  id: string
  label: string
  /** К чему приведёт выбор, например главы, на которые разделится книга. */
  details: { title: string; items: DetailItem[] } | null
}

export interface Question {
  id: string
  prompt: string
  options: QuestionOption[]
  default: string
  /** Каким вводам задан вопрос, ответ идёт каждому; подпись — когда вопрос про один ввод из нескольких. */
  input_indexes: number[]
  input_label: string | null
}

/** Существующая коллекция, новая по имени; ни то ни другое — без коллекции. */
export interface CollectionChoice {
  existing_id: number | null
  new_name: string | null
}

export interface NamingItem {
  label: string
  own_title: string
  words: number
}

export interface NamingVariable {
  token: string
  label: string
}

/** Добавление даёт несколько источников: backend спрашивает коллекцию и названия. */
export interface NamingRequired {
  heading: string
  items: NamingItem[]
  default_collection: CollectionChoice | null
  default_rule: string
  variables: NamingVariable[]
}

/** Как пользователь назвал источники: коллекция, правило и переписанные руками строки по номеру. */
export interface Naming {
  collection: CollectionChoice | null
  rule: string
  titles: Record<number, string>
}

export type AddSourceResult =
  | { questions: Question[] }
  | NamingRequired
  | { source_ids: number[]; collection_id: number | null }

/** Во что превратится ввод экрана Add. */
export type InputKind = 'source' | 'topic' | 'phrase'
/** Почему ввод заведомо не добавится. */
export type InputProblem = 'unsupported_link' | 'file_not_found'

/** Что backend сказал про ввод экрана Add; у пустого ввода все поля пустые. */
export interface InputDescription {
  kind: InputKind | null
  format: SourceFormat | null
  /** Несколько файлов разом. */
  several?: boolean | null
  label: string | null
  problem: InputProblem | null
  problem_message: string | null
  problem_hint: string | null
}

export interface SourceMediaStats {
  source_id: number
  source_title: string
  screenshot_bytes: number
  audio_bytes: number
  screenshot_count: number
  audio_count: number
}

export type CleanupMediaKind = 'all' | 'images' | 'audio'

export type FollowUpAction =
  | 'give_examples'
  | 'explain_detail'
  | 'explain_simpler'
  | 'how_to_say'
  | 'free_question'

export interface AnkiTemplates {
  front: string
  back: string
  cloze_front: string
  cloze_back: string
  css: string
}

export interface JobTypeCounts {
  job_type: string
  queued: number
  running: number
  failed: number
}

export interface QueueJob {
  job_id: number
  job_type: string
  source_id: number
  source_title: string
  status: 'running' | 'queued'
  position: number | null
  candidate_id: number | null
  target: string | null
}

export interface FailedSource {
  source_id: number
  source_title: string
  count: number
}

export interface FailedGroup {
  error_text: string
  count: number
  sources: FailedSource[]
}

export interface FailedByJobType {
  job_type: string
  total_failed: number
  groups: FailedGroup[]
}

export interface QueueSnapshot {
  counts: JobTypeCounts[]
  total_queued: number
  total_running: number
  total_failed: number
  running: QueueJob[]
  queued: QueueJob[]
  failed: FailedByJobType[]
}

/** Which jobs a queue action applies to; every field left out matches everything. */
export interface QueueSelection {
  job_type?: string
  source_id?: number
  job_id?: number
  error_text?: string
}

export interface QueueActionResult {
  affected: number
}

export interface BootstrapStatus {
  status: 'none' | 'building' | 'ready' | 'error'
  error: string | null
  built_at: string | null
  word_count: number
}

export interface BootstrapWord {
  lemma: string
  cefr_level: string
  zipf_value: number
}

export type UsagePeriod = 'today' | '7d' | '30d' | 'all'

export type AIFeature =
  | 'meaning_batch'
  | 'meaning_single'
  | 'meaning_follow_up'
  | 'phrase_polish'
  | 'topic_targets'

export interface TokenCounts {
  total: number
  sent_uncached: number
  cache_write: number
  cache_read: number
  answer: number
}

export interface AIUsageTotals {
  tokens: TokenCounts
  requests: number
  failed_requests: number
  change_percent: number | null
  tokens_per_meaning: number | null
}

export interface FeatureTokens {
  feature: AIFeature
  tokens: number
}

export interface AIUsageBucket {
  start: string
  total_tokens: number
  features: FeatureTokens[]
}

export interface AIUsageFeature {
  feature: AIFeature
  tokens: TokenCounts
  requests: number
  failed_requests: number
  items: number
  share_percent: number
}

export interface AIUsageStats {
  period: UsagePeriod
  bucket_size: 'hour' | 'day'
  tracking_since: string | null
  totals: AIUsageTotals
  buckets: AIUsageBucket[]
  features: AIUsageFeature[]
}
