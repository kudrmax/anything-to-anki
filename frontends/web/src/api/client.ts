import type {
  AnkiStatus,
  CardPreview,
  CandidateStatus,
  CreateNoteTypeResponse,
  KnownWord,
  Settings,
  SourceDetail,
  SourceStatus,
  SourceSummary,
  Stats,
  StoredCandidate,
  SyncResult,
  VerifyNoteTypeResponse,
} from './types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8002'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  createSource: (raw_text: string) =>
    req<{ id: number; status: string }>('/sources', {
      method: 'POST',
      body: JSON.stringify({ raw_text }),
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

  getStats: () => req<Stats>('/stats'),

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
}
