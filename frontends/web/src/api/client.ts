import type {
  AIUsageStats,
  AnkiStatus,
  AnkiTemplates,
  BootstrapStatus,
  BootstrapWord,
  CandidateSortOrder,
  CandidateStatus,
  CleanupMediaKind,
  ClozeDraft,
  ClozePreview,
  SaveClozeRequest,
  Collection,
  CollectionTree,
  DeletedCollection,
  MovedCollection,
  RenamedCollection,
  Scope,
  SourceBoard,
  SourcePlacement,
  ExportGroup,
  FollowUpAction,
  FrequentWordThresholdOption,
  GenerateMeaningResult,
  GenerationKind,
  GenerationOverview,
  GenerationScope,
  GlobalExport,
  ImageSearchResult,
  KnownWord,
  ReportReason,
  QueueActionResult,
  QueueSelection,
  QueueSnapshot,
  SourceOperation,
  Settings,
  SourceDetail,
  SourceMediaStats,
  SourceSummary,
  Stats,
  StoredCandidate,
  SyncResult,
  AddSourceResult,
  DetectedFormat,
  DocumentSelection,
  SourceDocument,
  UsagePeriod,
  NoteTypeCheck,
  NoteTypeKind,
  UnknownWord,
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
  addSource: (text: string, subtitlesPath: string, title: string, answers: Record<string, string>) =>
    req<AddSourceResult>('/sources/add', {
      method: 'POST',
      body: JSON.stringify({
        text,
        answers,
        ...(subtitlesPath ? { subtitles_path: subtitlesPath } : {}),
        ...(title ? { title } : {}),
      }),
    }),

  detectFormat: (text: string, signal?: AbortSignal) =>
    req<DetectedFormat>('/sources/detect-format', { method: 'POST', body: JSON.stringify({ text }), signal }),

  createTopic: (query: string, title?: string) =>
    req<{ id: number; status: string }>('/sources/topic', {
      method: 'POST',
      body: JSON.stringify({ query, ...(title ? { title } : {}) }),
    }),

  getSourceDocument: (sourceId: number) => req<SourceDocument>(`/sources/${sourceId}/document`),

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

  previewCloze: (id: number, draft: Partial<ClozeDraft>, signal?: AbortSignal) =>
    req<ClozePreview>(`/candidates/${id}/cloze/preview`, { method: 'POST', body: JSON.stringify(draft), signal }),

  saveCloze: (id: number, request: SaveClozeRequest) =>
    req<StoredCandidate>(`/candidates/${id}/cloze`, { method: 'PUT', body: JSON.stringify(request) }),

  markCandidate: (id: number, status: CandidateStatus) =>
    req<{ id: number; status: string }>(`/candidates/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),


  getAnkiStatus: () => req<AnkiStatus>('/anki/status'),

  getExportCards: (sourceId?: number, scope: Scope = 'all') =>
    req<GlobalExport>(
      sourceId != null ? `/export/cards/${sourceId}` : `/export/cards?${new URLSearchParams({ scope: String(scope) })}`,
    ),

  syncToAnki: (group: ExportGroup, sourceId?: number, scope: Scope = 'all') =>
    req<SyncResult>(
      sourceId != null
        ? `/export/sync-to-anki/${sourceId}?${new URLSearchParams({ group })}`
        : `/export/sync-to-anki?${new URLSearchParams({ group, scope: String(scope) })}`,
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

  getUnknownWords: () => req<UnknownWord[]>('/unknown-words'),

  deleteUnknownWord: (id: number) =>
    req<{ deleted: number }>(`/unknown-words/${id}`, { method: 'DELETE' }),

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

  rebuildSource: (sourceId: number, includeOpen: boolean) =>
    req<SourceOperation>(`/sources/${sourceId}/rebuild`, {
      method: 'POST',
      body: JSON.stringify({ include_open: includeOpen }),
    }),

  getStats: () => req<Stats>('/stats'),

  getUsage: (period: UsagePeriod, timezone: string) =>
    req<AIUsageStats>(`/api/usage?period=${period}&tz=${encodeURIComponent(timezone)}`),

  getNoteTypes: () => req<NoteTypeCheck[]>('/anki/note-types'),

  fixNoteType: (kind: NoteTypeKind) =>
    req<NoteTypeCheck>(`/anki/note-types/${kind}/fix`, { method: 'POST' }),

  setPhraseBoundary: (candidateId: number, selection: DocumentSelection) =>
    req<{ id: number; context_fragment: string }>(`/candidates/${candidateId}/phrase-boundary`, {
      method: 'PUT',
      body: JSON.stringify({ selection }),
    }),

  reportCandidate: (candidateId: number, reasons: string[], comment: string, unknownWords: number[]) =>
    req<unknown>(`/candidates/${candidateId}/report`, {
      method: 'POST',
      body: JSON.stringify({ reasons, comment, unknown_words: unknownWords }),
    }),

  getReportReasons: () => req<ReportReason[]>('/api/card-reports/reasons'),

  replaceWithExample: (candidateId: number, exampleText: string) =>
    req<StoredCandidate>(`/candidates/${candidateId}/replace-with-example`, {
      method: 'POST',
      body: JSON.stringify({ example_text: exampleText }),
    }),

  addSavedPhrase: (phrase: string, targetWords: number[]) =>
    req<StoredCandidate>('/sources/saved-phrases', {
      method: 'POST',
      body: JSON.stringify({ phrase, target_words: targetWords }),
    }),

  addManualCandidate: (sourceId: number, targetWords: number[], selection: DocumentSelection) =>
    req<StoredCandidate>(`/sources/${sourceId}/candidates/manual`, {
      method: 'POST',
      body: JSON.stringify({ target_words: targetWords, selection }),
    }),

  getMediaStats: () => req<SourceMediaStats[]>('/api/settings/media-stats'),

  cleanupMedia: (sourceId: number, kind: CleanupMediaKind) =>
    reqVoid('/api/settings/media-cleanup', {
      method: 'POST',
      body: JSON.stringify({ source_id: sourceId, kind }),
    }),

  getAnkiTemplates: () => req<AnkiTemplates>('/anki/templates'),

  getQueue: (sourceId: number | undefined, queuedLimit: number, signal?: AbortSignal) => {
    const params = new URLSearchParams({ queued_limit: String(queuedLimit) })
    if (sourceId != null) params.set('source_id', String(sourceId))
    return req<QueueSnapshot>(`/api/queue?${params.toString()}`, { signal })
  },

  cancelQueue: (selection: QueueSelection) => queueAction('cancel', selection),

  retryQueue: (selection: QueueSelection) => queueAction('retry', selection),

  dismissQueue: (selection: QueueSelection) => queueAction('dismiss', selection),

  getCollectionTree: () => req<CollectionTree>('/collections'),

  createCollection: (name: string, parentId: number | null = null) =>
    req<Collection>('/collections', { method: 'POST', body: JSON.stringify({ name, parent_id: parentId }) }),

  renameCollection: (id: number, name: string) =>
    req<RenamedCollection>(`/collections/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) }),

  moveCollection: (id: number, parentId: number | null, position: number) =>
    req<MovedCollection>(`/collections/${id}/move`, {
      method: 'POST',
      body: JSON.stringify({ parent_id: parentId, position }),
    }),

  deleteCollection: (id: number) => req<DeletedCollection>(`/collections/${id}`, { method: 'DELETE' }),

  restoreCollection: (id: number) => req<Collection>(`/collections/${id}/restore`, { method: 'POST' }),

  getSourceBoard: (scope: Scope, query: string, signal?: AbortSignal) =>
    req<SourceBoard>(`/sources/board?${new URLSearchParams({ scope: String(scope), query })}`, { signal }),

  placeSources: (placements: SourcePlacement[]) =>
    req<{ previous: SourcePlacement[] }>('/sources/placements', {
      method: 'POST',
      body: JSON.stringify({ placements }),
    }),

  processPending: (scope: Scope) =>
    req<{ started: number[]; skipped: number[] }>(`/sources/process-pending?${new URLSearchParams({ scope: String(scope) })}`, {
      method: 'POST',
    }),

  processSources: (sourceIds: number[]) =>
    req<{ started: number[]; skipped: number[] }>('/sources/process-batch', {
      method: 'POST',
      body: JSON.stringify({ source_ids: sourceIds }),
    }),

  deleteSources: (sourceIds: number[]) =>
    req<{ deleted: number[]; skipped: number[] }>('/sources/delete-batch', {
      method: 'POST',
      body: JSON.stringify({ source_ids: sourceIds }),
    }),

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
