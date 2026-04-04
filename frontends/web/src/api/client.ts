import type { AnkiStatus, CardPreview, CandidateStatus, Settings, SourceDetail, SourceStatus, SourceSummary, StoredCandidate, SyncResult } from './types'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

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

  updateSettings: (patch: Partial<Pick<Settings, 'cefr_level' | 'anki_deck_name'>>) =>
    req<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(patch) }),
}
