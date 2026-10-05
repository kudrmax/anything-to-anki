export type SourceStatus =
  | 'new'
  | 'processing'
  | 'done'
  | 'error'
  | 'partially_reviewed'
  | 'reviewed'

export type InputMethod = 'text_pasted' | 'lyrics_pasted' | 'subtitles_file' | 'video_file' | 'youtube_url' | 'topic_query' | 'phrase_added'
export type ContentType = 'text' | 'lyrics' | 'video' | 'topic' | 'phrases'
export type SourceType = InputMethod

export type ProcessingStage = 'cleaning_source' | 'analyzing_text' | 'mapping_timecodes' | 'collecting_phrases'

export type CandidateStatus = 'pending' | 'learn' | 'known' | 'skip'

export type CandidateSortOrder = 'relevance' | 'chronological' | 'key_words'

export interface Collection {
  id: number
  name: string
  source_count: number
  created_at: string
}

export interface SourceSummary {
  id: number
  title: string
  raw_text_preview: string
  status: SourceStatus
  source_type: SourceType
  content_type: ContentType
  source_url: string | null
  video_downloaded: boolean
  created_at: string
  candidate_count: number
  learn_count: number
  /** Сколько фраз уже получили решение: learn, known или skip. */
  decided_count: number
  processing_stage: ProcessingStage | null
  collection_id: number | null
  collection_name: string | null
  /** Тема ещё ждёт AI-шага: запрос не превращён в target'ы. */
  awaiting_generation: boolean
  generation_status: GenerationStatus | null
  generation_error: string | null
  /** Встроенный источник: его нельзя удалить и переобработать. */
  is_permanent: boolean
}

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

export interface StoredCandidate {
  id: number
  lemma: string
  pos: string
  cefr_level: string | null
  zipf_frequency: number
  is_sweet_spot: boolean
  /** На карточку уже жаловались. */
  reported: boolean
  /** Фраза как в источнике. */
  context_fragment: string
  /** Фраза карточки: упрощённая AI, если её не откатили. */
  phrase: string
  /** Упрощённая AI фраза — только если она отличается от фразы источника. */
  polished_fragment: string | null
  polish_reverted: boolean
  /** AI ещё работает над фразой. */
  polish_status: EnrichmentStatus | null
  fragment_purity: string
  occurrences: number
  status: CandidateStatus
  surface_form: string | null
  is_phrasal_verb: boolean
  has_custom_context_fragment: boolean
  meaning: CandidateMeaning | null
  media: CandidateMedia | null
  pronunciation: CandidatePronunciation | null
  tts: CandidateTTS | null
  cefr_breakdown?: CEFRBreakdown | null
  frequency_band: string | null
  usage_distribution: Record<string, number> | null
  origin: PhraseOrigin | null
}

export interface SourceDetail {
  id: number
  title: string
  raw_text: string
  cleaned_text: string | null
  status: SourceStatus
  source_type: SourceType
  content_type: ContentType
  can_polish_phrases: boolean
  /** Есть ли у источника свой текст, который показывает ревью. */
  has_source_text: boolean
  source_url: string | null
  video_downloaded: boolean
  error_message: string | null
  processing_stage: ProcessingStage | null
  created_at: string
  candidates: StoredCandidate[]
  /** How many candidates to show before "Show more"; null — show all. */
  initially_shown_candidates: number | null
}

export interface AnkiStatus {
  available: boolean
  version: number | null
}

export interface CardPreview {
  candidate_id: number
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
}

export interface ExportSection {
  source_id: number
  source_title: string
  cards: CardPreview[]
}

export interface GlobalExport {
  sections: ExportSection[]
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

export interface Settings {
  cefr_level: string
  frequent_word_threshold: string
  anki_deck_name: string
  ai_provider: string
  ai_model: string
  anki_note_type: string
  anki_field_sentence: string
  anki_field_target_word: string
  anki_field_meaning: string
  anki_field_ipa: string
  anki_field_image: string
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
}

export interface FrequentWordThresholdOption {
  value: string
  /** The threshold itself; for Auto — its current value calibrated on your marks. */
  zipf: number | null
  /** Words that go down to the bottom of the list at this threshold. */
  examples: string[]
}

export interface KnownWord {
  id: number
  lemma: string
  pos: string | null
  created_at: string
}

export interface Stats {
  learn_count: number
  candidate_count: number
  known_word_count: number
}

export interface VerifyNoteTypeResponse {
  valid: boolean
  available_fields: string[]
  missing_fields: string[]
}

export interface CreateNoteTypeResponse {
  already_existed: boolean
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

/** missing — cards nothing was made for yet; failed — cards whose last attempt failed; all — every card, replacing results. */
export type GenerationScope = 'missing' | 'failed' | 'all'

export type GenerationBlocker = 'video_not_downloaded' | 'video_downloading'

/** done + running + failed + missing === total */
export interface GenerationKindStatus {
  kind: GenerationKind
  total: number
  done: number
  running: number
  failed: number
  missing: number
  blocked_by: GenerationBlocker | null
}

/** Фоновая генерация по карточкам источника. */
export interface GenerationOverview {
  kinds: GenerationKindStatus[]
  in_progress: boolean
}

export interface ReprocessStats {
  learn_count: number
  known_count: number
  skip_count: number
  pending_count: number
  has_active_jobs: boolean
}

export interface SubtitleTrack {
  index: number
  language: string | null
  title: string | null
  codec: string
}

export interface AudioTrack {
  index: number
  language: string | null
  title: string | null
  codec: string
  channels: number | null
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
