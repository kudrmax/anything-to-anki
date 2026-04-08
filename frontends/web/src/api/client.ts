import type {
  AnkiStatus,
  CardPreview,
  CandidateSortOrder,
  CandidateStatus,
  CleanupMediaKind,
  CreateNoteTypeResponse,
  GenerateMeaningResult,
  KnownWord,
  QueueSummary,
  Settings,
  SourceDetail,
  SourceMediaStats,
  SourceStatus,
  SourceSummary,
  SourceType,
  Stats,
  StoredCandidate,
  SubtitleTrack,
  AudioTrack,
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
  createSource: (raw_text: string, source_type: SourceType, title?: string) =>
    req<{ id: number; status: string }>('/sources', {
      method: 'POST',
      body: JSON.stringify({ raw_text, source_type, ...(title ? { title } : {}) }),
    }),

  renameSource: (id: number, title: string) =>
    req<{ id: number; title: string }>(`/sources/${id}/title`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  listSources: () => req<SourceSummary[]>('/sources'),

  getSource: (id: number, sort: CandidateSortOrder = 'relevance') =>
    req<SourceDetail>(`/sources/${id}?sort=${sort}`),

  processSource: (id: number) =>
    req<{ status: string }>(`/sources/${id}/process`, { method: 'POST' }),

  getCandidates: (id: number, sort: CandidateSortOrder = 'relevance') =>
    req<StoredCandidate[]>(`/sources/${id}/candidates?sort=${sort}`),

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

  getSettings: () => req<Settings>('/api/settings'),

  updateSettings: (patch: Partial<Settings>) =>
    req<Settings>('/api/settings', { method: 'PATCH', body: JSON.stringify(patch) }),

  getKnownWords: () => req<KnownWord[]>('/known-words'),

  deleteKnownWord: (id: number) =>
    req<{ deleted: number }>(`/known-words/${id}`, { method: 'DELETE' }),

  deleteSource: (id: number) => reqVoid(`/sources/${id}`, { method: 'DELETE' }),

  generateMeaning: (candidateId: number) =>
    req<GenerateMeaningResult>(`/candidates/${candidateId}/generate-meaning`, { method: 'POST' }),

  regenerateCandidateMedia: (candidateId: number) =>
    req<{ status: string }>(`/candidates/${candidateId}/regenerate-media`, { method: 'POST' }),

  enqueueMeaningGeneration: (sourceId: number, sort: CandidateSortOrder = 'relevance') =>
    req<{ enqueued: number; batches: number }>(
      `/sources/${sourceId}/meanings/generate?sort=${sort}`,
      { method: 'POST' },
    ),

  cancelMeaningQueue: (sourceId: number) =>
    req<{ cancelled: number }>(`/sources/${sourceId}/meanings/cancel`, { method: 'POST' }),

  retryFailedMeanings: (sourceId: number) =>
    req<{ enqueued: number }>(`/sources/${sourceId}/meanings/retry-failed`, { method: 'POST' }),

  enqueueMediaGeneration: (sourceId: number, sort: CandidateSortOrder = 'relevance') =>
    req<{ enqueued: number }>(
      `/sources/${sourceId}/media/generate?sort=${sort}`,
      { method: 'POST' },
    ),

  cancelMediaQueue: (sourceId: number) =>
    req<{ cancelled: number }>(`/sources/${sourceId}/media/cancel`, { method: 'POST' }),

  retryFailedMedia: (sourceId: number) =>
    req<{ enqueued: number }>(`/sources/${sourceId}/media/retry-failed`, { method: 'POST' }),

  getQueueSummary: (sourceId: number) =>
    req<QueueSummary>(`/sources/${sourceId}/queue-summary`),

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

  getMediaStats: () => req<SourceMediaStats[]>('/api/settings/media-stats'),

  cleanupMedia: (sourceId: number, kind: CleanupMediaKind) =>
    reqVoid('/api/settings/media-cleanup', {
      method: 'POST',
      body: JSON.stringify({ source_id: sourceId, kind }),
    }),

  createVideoSource: async (
    videoFile: File,
    srtFile: File | null,
    title: string | undefined,
    subtitleTrackIndex: number | undefined,
    audioTrackIndex: number | undefined,
  ): Promise<{
    id?: number
    status: string
    subtitle_tracks?: SubtitleTrack[]
    audio_tracks?: AudioTrack[]
    pending_video_path?: string
  }> => {
    const form = new FormData()
    form.append('video', videoFile)
    if (srtFile) form.append('srt', srtFile)
    if (title) form.append('title', title)
    if (subtitleTrackIndex !== undefined) form.append('subtitle_track_index', String(subtitleTrackIndex))
    if (audioTrackIndex !== undefined) form.append('audio_track_index', String(audioTrackIndex))
    const res = await fetch(`${BASE}/sources/video`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
    return res.json() as Promise<{
      id?: number
      status: string
      subtitle_tracks?: SubtitleTrack[]
      audio_tracks?: AudioTrack[]
      pending_video_path?: string
    }>
  },
}
