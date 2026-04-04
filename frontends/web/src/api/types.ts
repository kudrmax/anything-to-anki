export type SourceStatus =
  | 'new'
  | 'processing'
  | 'done'
  | 'error'
  | 'partially_reviewed'
  | 'reviewed'

export type CandidateStatus = 'pending' | 'learn' | 'known' | 'skip'

export interface SourceSummary {
  id: number
  raw_text_preview: string
  status: SourceStatus
  created_at: string
  candidate_count: number
  learn_count: number
}

export interface StoredCandidate {
  id: number
  lemma: string
  pos: string
  cefr_level: string
  zipf_frequency: number
  is_sweet_spot: boolean
  context_fragment: string
  fragment_purity: string
  occurrences: number
  status: CandidateStatus
}

export interface SourceDetail {
  id: number
  raw_text: string
  cleaned_text: string | null
  status: SourceStatus
  error_message: string | null
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
}
