export type SourceStatus =
  | 'new'
  | 'processing'
  | 'done'
  | 'error'
  | 'partially_reviewed'
  | 'reviewed'

export type InputMethod = 'text_pasted' | 'lyrics_pasted' | 'subtitles_file' | 'video_file' | 'youtube_url'
export type ContentType = 'text' | 'lyrics' | 'video'
export type SourceType = InputMethod

export type ProcessingStage = 'cleaning_source' | 'analyzing_text'

export type CandidateStatus = 'pending' | 'learn' | 'known' | 'skip'

export type CandidateSortOrder = 'relevance' | 'chronological'

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
  processing_stage: ProcessingStage | null
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

export interface StoredCandidate {
  id: number
  lemma: string
  pos: string
  cefr_level: string | null
  zipf_frequency: number
  is_sweet_spot: boolean
  context_fragment: string
  fragment_purity: string
  occurrences: number
  status: CandidateStatus
  surface_form: string | null
  is_phrasal_verb: boolean
  has_custom_context_fragment: boolean
  meaning: CandidateMeaning | null
  media: CandidateMedia | null
  pronunciation: CandidatePronunciation | null
  cefr_breakdown?: CEFRBreakdown | null
  frequency_band: string | null
  usage_distribution: Record<string, number> | null
}

export interface SourceDetail {
  id: number
  title: string
  raw_text: string
  cleaned_text: string | null
  status: SourceStatus
  source_type: SourceType
  content_type: ContentType
  source_url: string | null
  video_downloaded: boolean
  error_message: string | null
  processing_stage: ProcessingStage | null
  created_at: string
  candidates: StoredCandidate[]
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
}

export interface ExportSection {
  source_id: number
  source_title: string
  cards: CardPreview[]
}

export interface GlobalExport {
  sections: ExportSection[]
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
}

export interface KnownWord {
  id: number
  lemma: string
  pos: string
  created_at: string
}

export interface Stats {
  learn_count: number
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

export interface QueueStatus {
  queued: number
  running: number
  failed: number
}

export interface QueueSummary {
  meaning: QueueStatus
  media: QueueStatus
  pronunciation: QueueStatus
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
