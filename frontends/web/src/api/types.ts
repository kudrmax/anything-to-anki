export type SourceStatus =
  | 'new'
  | 'processing'
  | 'done'
  | 'error'
  | 'partially_reviewed'
  | 'reviewed'

export type SourceType = 'text' | 'lyrics' | 'subtitles' | 'book' | 'video' | 'article'

export type ProcessingStage = 'cleaning_source' | 'analyzing_text'

export type CandidateStatus = 'pending' | 'learn' | 'known' | 'skip'

export interface SourceSummary {
  id: number
  title: string
  raw_text_preview: string
  status: SourceStatus
  source_type: SourceType
  created_at: string
  candidate_count: number
  learn_count: number
  processing_stage: ProcessingStage | null
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
  meaning: string | null
  ipa: string | null
  is_phrasal_verb: boolean
}

export interface SourceDetail {
  id: number
  title: string
  raw_text: string
  cleaned_text: string | null
  status: SourceStatus
  source_type: SourceType
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
  ipa: string | null
  screenshot_url: string | null
  audio_url: string | null
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

export interface PromptTemplate {
  id: number
  function_key: string
  system_prompt: string
  user_template: string
}

export const PROMPT_LABELS: Record<string, { name: string; description: string }> = {
  generate_meaning: {
    name: 'Meaning generation',
    description: 'Explains a word based on the context it appears in',
  },
}

export interface GenerateMeaningResult {
  candidate_id: number
  meaning: string
  ipa: string | null
  tokens_used: number
}

export interface GenerationJobStatus {
  id: number
  source_id: number | null
  status: 'pending' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed'
  total_candidates: number
  processed_candidates: number
  failed_candidates: number
  skipped_candidates: number
  candidate_ids: number[]
  created_at: string
}

export interface GenerationQueueStatus {
  running_job: GenerationJobStatus | null
  pending_jobs: GenerationJobStatus[]
  total_pending_count: number
}

export interface SubtitleTrack {
  index: number
  language: string | null
  title: string | null
  codec: string
}
