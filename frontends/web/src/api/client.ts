import type {
  AnkiStatus,
  CardPreview,
  CandidateStatus,
  CreateNoteTypeResponse,
  GenerateAllMeaningsResult,
  GenerateMeaningResult,
  KnownWord,
  PromptTemplate,
  Settings,
  SourceDetail,
  SourceStatus,
  SourceSummary,
  SourceType,
  Stats,
  StoredCandidate,
  SyncResult,
  VerifyNoteTypeResponse,
} from './types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

async function reqVoid(path: string, init?: RequestInit): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
}

export const api = {
  createSource: (raw_text: string, source_type: SourceType) =>
    req<{ id: number; status: string }>('/sources', {
      method: 'POST',
      body: JSON.stringify({ raw_text, source_type }),
    }),

  listSources: () => req<SourceSummary[]>('/sources'),

  getSource: (id: number) => req<SourceDetail>(`/sources/${id}`),

  processSource: (id: number) =>
    req<{ status: string }>(`/sources/${id}/process`, { method: 'POST' }),

  getCandidates: (id: number) => req<StoredCandidate[]>(`/sources/${id}/candidates`),

  markCandidate: (id: number, status: CandidateStatus) =>
    req<{ id: number; status: string }>(`/candidates/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  updateSourceStatus: (id: number, status: SourceStatus) =>
    req<{ id: number; status: string }>(`/sources/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  getAnkiStatus: () => req<AnkiStatus>('/anki/status'),

  getSourceCards: (id: number) => req<CardPreview[]>(`/sources/${id}/cards`),

  syncToAnki: (id: number) =>
    req<SyncResult>(`/sources/${id}/sync-to-anki`, { method: 'POST' }),

  getSettings: () => req<Settings>('/settings'),

  updateSettings: (patch: Partial<Settings>) =>
    req<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(patch) }),

  getKnownWords: () => req<KnownWord[]>('/known-words'),

  deleteKnownWord: (id: number) =>
    req<{ deleted: number }>(`/known-words/${id}`, { method: 'DELETE' }),

  deleteSource: (id: number) => reqVoid(`/sources/${id}`, { method: 'DELETE' }),

  generateMeaning: (candidateId: number) =>
    req<GenerateMeaningResult>(`/candidates/${candidateId}/generate-meaning`, { method: 'POST' }),

  generateAllMeanings: (sourceId: number, status?: string) =>
    req<GenerateAllMeaningsResult>(
      `/sources/${sourceId}/generate-all-meanings${status ? `?status=${status}` : ''}`,
      { method: 'POST' },
    ),

  getStats: () => req<Stats>('/stats'),

  getPrompts: () => req<PromptTemplate[]>('/prompts'),

  updatePrompt: (functionKey: string, data: { system_prompt: string; user_template: string }) =>
    req<PromptTemplate>(`/prompts/${functionKey}`, { method: 'PUT', body: JSON.stringify(data) }),

  verifyNoteType: (note_type: string, required_fields: string[]) =>
    req<VerifyNoteTypeResponse>('/anki/verify-note-type', {
      method: 'POST',
      body: JSON.stringify({ note_type, required_fields }),
    }),

  createNoteType: (note_type: string, fields: string[]) =>
    req<CreateNoteTypeResponse>('/anki/create-note-type', {
      method: 'POST',
      body: JSON.stringify({ note_type, fields }),
    }),

  updateCandidateFragment: (candidateId: number, contextFragment: string) =>
    req<{ id: number; context_fragment: string }>(`/candidates/${candidateId}/context-fragment`, {
      method: 'PATCH',
      body: JSON.stringify({ context_fragment: contextFragment }),
    }),

  addManualCandidate: (sourceId: number, surfaceForm: string, contextFragment: string) =>
    req<StoredCandidate>(`/sources/${sourceId}/candidates/manual`, {
      method: 'POST',
      body: JSON.stringify({ surface_form: surfaceForm, context_fragment: contextFragment }),
    }),
}
