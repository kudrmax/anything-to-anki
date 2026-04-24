import type {
  AnkiStatus,
  AnkiTemplates,
  CandidateSortOrder,
  CandidateStatus,
  CleanupMediaKind,
  Collection,
  CreateNoteTypeResponse,
  FollowUpAction,
  GenerateMeaningResult,
  GlobalExport,
  KnownWord,
  QueueFailed,
  QueueGlobalSummary,
  QueueOrder,
  QueueSummary,
  ReprocessStats,
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

  createUrlSource: (url: string, title?: string) =>
    req<{ id: number; status: string }>('/sources/url', {
      method: 'POST',
      body: JSON.stringify({ url, ...(title ? { title } : {}) }),
    }),

  renameSource: (id: number, title: string) =>
    req<{ id: number; title: string }>(`/sources/${id}/title`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  listSources: (collectionId?: number) =>
    req<SourceSummary[]>(
      collectionId != null ? `/sources?collection_id=${collectionId}` : '/sources',
    ),

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

  getExportCards: (sourceId?: number) =>
    req<GlobalExport>(sourceId != null ? `/export/cards/${sourceId}` : '/export/cards'),

  syncToAnki: (sourceId?: number) =>
    req<SyncResult>(
      sourceId != null ? `/export/sync-to-anki/${sourceId}` : '/export/sync-to-anki',
      { method: 'POST' },
    ),

  getSettings: () => req<Settings>('/api/settings'),

  updateSettings: (patch: Partial<Settings>) =>
    req<Settings>('/api/settings', { method: 'PATCH', body: JSON.stringify(patch) }),

  getKnownWords: () => req<KnownWord[]>('/known-words'),

  deleteKnownWord: (id: number) =>
    req<{ deleted: number }>(`/known-words/${id}`, { method: 'DELETE' }),

  deleteSource: (id: number) => reqVoid(`/sources/${id}`, { method: 'DELETE' }),

  generateMeaning: (candidateId: number, followUpAction?: FollowUpAction, followUpText?: string) =>
    req<GenerateMeaningResult>(`/candidates/${candidateId}/generate-meaning`, {
      method: 'POST',
      body: followUpAction
        ? JSON.stringify({ action: followUpAction, ...(followUpText ? { text: followUpText } : {}) })
        : undefined,
    }),

  regenerateCandidateMedia: (candidateId: number) =>
    req<{ status: string }>(`/candidates/${candidateId}/regenerate-media`, { method: 'POST' }),

  downloadVideo: (sourceId: number) =>
    req<{ status: string }>(`/sources/${sourceId}/download-video`, { method: 'POST' }),

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

  enqueuePronunciationDownload: (sourceId: number) =>
    req<{ enqueued: number }>(
      `/sources/${sourceId}/pronunciation/generate`,
      { method: 'POST' },
    ),

  cancelPronunciationQueue: (sourceId: number) =>
    req<{ cancelled: number }>(`/sources/${sourceId}/pronunciation/cancel`, { method: 'POST' }),

  retryFailedPronunciation: (sourceId: number) =>
    req<{ enqueued: number }>(`/sources/${sourceId}/pronunciation/retry-failed`, { method: 'POST' }),

  enqueueTTSGeneration: (sourceId: number) =>
    req<{ enqueued: number }>(
      `/sources/${sourceId}/tts/generate`,
      { method: 'POST' },
    ),

  cancelTTSQueue: (sourceId: number) =>
    req<{ cancelled: number }>(`/sources/${sourceId}/tts/cancel`, { method: 'POST' }),

  retryFailedTTS: (sourceId: number) =>
    req<{ enqueued: number }>(`/sources/${sourceId}/tts/retry-failed`, { method: 'POST' }),

  generateCandidateTTS: (candidateId: number) =>
    req<{ status: string }>(`/candidates/${candidateId}/generate-tts`, { method: 'POST' }),

  getQueueSummary: (sourceId: number) =>
    req<QueueSummary>(`/sources/${sourceId}/queue-summary`),

  getReprocessStats: (sourceId: number) =>
    req<ReprocessStats>(`/sources/${sourceId}/reprocess-stats`),

  reprocessSource: (sourceId: number) =>
    req<{ status: string }>(`/sources/${sourceId}/reprocess`, { method: 'POST' }),

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

  replaceWithExample: (candidateId: number, exampleText: string) =>
    req<StoredCandidate>(`/candidates/${candidateId}/replace-with-example`, {
      method: 'POST',
      body: JSON.stringify({ example_text: exampleText }),
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

  createFileSource: async (
    filePath: string,
    srtPath: string | undefined,
    title: string | undefined,
    subtitleTrackIndex: number | undefined,
    audioTrackIndex: number | undefined,
  ): Promise<{
    id?: number
    status: string
    subtitle_tracks?: SubtitleTrack[]
    audio_tracks?: AudioTrack[]
    file_path?: string
    srt_path?: string
  }> => {
    const body: Record<string, unknown> = { file_path: filePath }
    if (srtPath) body.srt_path = srtPath
    if (title) body.title = title
    if (subtitleTrackIndex !== undefined) body.subtitle_track_index = subtitleTrackIndex
    if (audioTrackIndex !== undefined) body.audio_track_index = audioTrackIndex
    const res = await fetch(`${BASE}/sources/file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => null)
      throw new Error(err?.detail ?? res.statusText)
    }
    return res.json()
  },

  getAnkiTemplates: () => req<AnkiTemplates>('/anki/templates'),

  getQueueGlobalSummary: (sourceId?: number) =>
    req<QueueGlobalSummary>(`/api/queue/global-summary${sourceId != null ? `?source_id=${sourceId}` : ''}`),

  getQueueOrder: (sourceId?: number, limit = 50) => {
    const params = new URLSearchParams()
    if (sourceId != null) params.set('source_id', String(sourceId))
    params.set('limit', String(limit))
    return req<QueueOrder>(`/api/queue/order?${params.toString()}`)
  },

  getQueueFailed: (sourceId?: number) =>
    req<QueueFailed>(`/api/queue/failed${sourceId != null ? `?source_id=${sourceId}` : ''}`),

  retryQueue: (jobType: string, sourceId?: number, errorText?: string) =>
    req<{ retried: number }>('/api/queue/retry', {
      method: 'POST',
      body: JSON.stringify({
        job_type: jobType,
        source_id: sourceId ?? null,
        error_text: errorText ?? null,
      }),
    }),

  cancelQueue: (jobType: string, sourceId?: number, jobId?: number) =>
    req<{ cancelled: number }>('/api/queue/cancel', {
      method: 'POST',
      body: JSON.stringify({
        job_type: jobType,
        source_id: sourceId ?? null,
        job_id: jobId ?? null,
      }),
    }),

  listCollections: () => req<Collection[]>('/collections'),

  createCollection: (name: string) =>
    req<Collection>('/collections', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  renameCollection: (id: number, name: string) =>
    req<Collection>(`/collections/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),

  deleteCollection: (id: number) =>
    reqVoid(`/collections/${id}`, { method: 'DELETE' }),

  assignSourceCollection: (sourceId: number, collectionId: number | null) =>
    req<{ source_id: number; collection_id: number | null }>(
      `/sources/${sourceId}/collection`,
      {
        method: 'PATCH',
        body: JSON.stringify({ collection_id: collectionId }),
      },
    ),
}
