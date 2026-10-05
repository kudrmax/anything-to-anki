import type {
  AIUsageStats,
  AnkiStatus,
  AnkiTemplates,
  BootstrapStatus,
  BootstrapWord,
  CandidateSortOrder,
  CandidateStatus,
  CleanupMediaKind,
  Collection,
  CreateNoteTypeResponse,
  FollowUpAction,
  FrequentWordThresholdOption,
  GenerateMeaningResult,
  GenerationKind,
  GenerationOverview,
  GenerationScope,
  GlobalExport,
  ImageSearchResult,
  KnownWord,
  QueueActionResult,
  QueueSelection,
  QueueSnapshot,
  ReprocessStats,
  Settings,
  SourceDetail,
  SourceMediaStats,
  SourceSummary,
  SourceType,
  Stats,
  StoredCandidate,
  SubtitleTrack,
  AudioTrack,
  SyncResult,
  UsagePeriod,
  VerifyNoteTypeResponse,
} from './types'
import { buildHeaders, reloadIfStale } from './clientBuild'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

async function send(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...buildHeaders() },
    ...init,
  })
  reloadIfStale(res)
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await send(path, init)
  return res.json() as Promise<T>
}

async function reqVoid(path: string, init?: RequestInit): Promise<void> {
  await send(path, init)
}

function queueAction(action: 'cancel' | 'retry' | 'dismiss', selection: QueueSelection): Promise<QueueActionResult> {
  return req<QueueActionResult>(`/api/queue/${action}`, { method: 'POST', body: JSON.stringify(selection) })
}

export const api = {
  createSource: (raw_text: string, input_method: SourceType, title?: string) =>
    req<{ id: number; status: string }>('/sources', {
      method: 'POST',
      body: JSON.stringify({ raw_text, input_method, ...(title ? { title } : {}) }),
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

  getFrequentWordThresholds: () =>
    req<FrequentWordThresholdOption[]>('/api/settings/frequent-word-thresholds'),

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

  searchTargetImages: (candidateId: number, query?: string) =>
    req<ImageSearchResult>(`/candidates/${candidateId}/image-options${query === undefined ? '' : `?${new URLSearchParams({ query })}`}`),

  applyTargetImage: (candidateId: number, url: string) =>
    req<{ status: string }>(`/candidates/${candidateId}/image`, { method: 'PUT', body: JSON.stringify({ url }) }),

  pasteTargetImage: (candidateId: number, picture: Blob) =>
    req<{ status: string }>(`/candidates/${candidateId}/image/pasted`, {
      method: 'PUT',
      headers: { 'Content-Type': picture.type, ...buildHeaders() },
      body: picture,
    }),

  downloadVideo: (sourceId: number) =>
    req<{ status: string }>(`/sources/${sourceId}/download-video`, { method: 'POST' }),

  polishPhraseAgain: (candidateId: number) =>
    req<{ status: string }>(`/candidates/${candidateId}/polish`, { method: 'POST' }),

  setPolishReverted: (candidateId: number, reverted: boolean) =>
    req<{ id: number; reverted: boolean }>(`/candidates/${candidateId}/polish/reverted`, {
      method: 'PUT',
      body: JSON.stringify({ reverted }),
    }),

  editPhrase: (candidateId: number, phrase: string) =>
    req<{ id: number }>(`/candidates/${candidateId}/phrase`, {
      method: 'PUT',
      body: JSON.stringify({ phrase }),
    }),

  generateCandidateTTS: (candidateId: number) =>
    req<{ status: string }>(`/candidates/${candidateId}/generate-tts`, { method: 'POST' }),

  enqueueTopicGeneration: (sourceId: number) =>
    req<{ status: string }>(`/sources/${sourceId}/topic-targets/generate`, { method: 'POST' }),

  getGenerationStatus: (sourceId: number) =>
    req<GenerationOverview>(`/sources/${sourceId}/generation`),

  runGeneration: (sourceId: number, kind: GenerationKind, scope: GenerationScope, sort: CandidateSortOrder = 'relevance') =>
    req<{ enqueued: number }>(
      `/sources/${sourceId}/generation/${kind}?scope=${scope}&sort=${sort}`,
      { method: 'POST' },
    ),

  cancelGeneration: (sourceId: number, kind: GenerationKind) =>
    req<{ cancelled: number }>(`/sources/${sourceId}/generation/${kind}/cancel`, { method: 'POST' }),

  getReprocessStats: (sourceId: number) =>
    req<ReprocessStats>(`/sources/${sourceId}/reprocess-stats`),

  reprocessSource: (sourceId: number) =>
    req<{ status: string }>(`/sources/${sourceId}/reprocess`, { method: 'POST' }),

  getStats: () => req<Stats>('/stats'),

  getUsage: (period: UsagePeriod, timezone: string) =>
    req<AIUsageStats>(`/api/usage?period=${period}&tz=${encodeURIComponent(timezone)}`),

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

  reportCandidate: (candidateId: number, reasons: string[], comment: string) =>
    req<unknown>(`/candidates/${candidateId}/report`, {
      method: 'POST',
      body: JSON.stringify({ reasons, comment }),
    }),

  getReportReasons: () => req<string[]>('/api/card-reports/reasons'),

  replaceWithExample: (candidateId: number, exampleText: string) =>
    req<StoredCandidate>(`/candidates/${candidateId}/replace-with-example`, {
      method: 'POST',
      body: JSON.stringify({ example_text: exampleText }),
    }),

  addSavedPhrase: (phrase: string, target: string) =>
    req<StoredCandidate>('/sources/saved-phrases', {
      method: 'POST',
      body: JSON.stringify({ phrase, target }),
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

  getQueue: (sourceId: number | undefined, queuedLimit: number, signal?: AbortSignal) => {
    const params = new URLSearchParams({ queued_limit: String(queuedLimit) })
    if (sourceId != null) params.set('source_id', String(sourceId))
    return req<QueueSnapshot>(`/api/queue?${params.toString()}`, { signal })
  },

  cancelQueue: (selection: QueueSelection) => queueAction('cancel', selection),

  retryQueue: (selection: QueueSelection) => queueAction('retry', selection),

  dismissQueue: (selection: QueueSelection) => queueAction('dismiss', selection),

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

  getBootstrapStatus: () => req<BootstrapStatus>('/api/bootstrap/status'),

  startBootstrapBuild: () =>
    req<{ status: string }>('/api/bootstrap/build', { method: 'POST' }),

  getBootstrapWords: (excluded: string[]) =>
    req<BootstrapWord[]>('/api/bootstrap/words', {
      method: 'POST',
      body: JSON.stringify({ excluded }),
    }),

  saveBootstrapKnown: (lemmas: string[]) =>
    req<{ saved: number }>('/api/bootstrap/known', {
      method: 'POST',
      body: JSON.stringify({ lemmas }),
    }),
}
