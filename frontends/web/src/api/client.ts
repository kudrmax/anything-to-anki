import type {
  AIUsageStats,
  AnkiStatus,
  AnkiTemplates,
  BootstrapStatus,
  BootstrapWord,
  CandidateSortOrder,
  DecisionButton,
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
  GenerationKind,
  GenerationOverview,
  GenerationScope,
  GlobalExport,
  ImageSearchResult,
  KnownWord,
  LearningWords,
  ReportReason,
  QueueActionResult,
  QueueSelection,
  QueueSnapshot,
  RebuildMode,
  SourceOperation,
  Settings,
  ReviewDetail,
  SetScope,
  SourceMediaStats,
  SourceSummary,
  Stats,
  StoredCandidate,
  SyncResult,
  AddSourceResult,
  Naming,
  InputDescription,
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
  addSource: (text: string, subtitlesPath: string, title: string, answers: Record<string, string>[], naming?: Naming) =>
    req<AddSourceResult>('/sources/add', {
      method: 'POST',
      body: JSON.stringify({
        text,
        answers,
        ...(subtitlesPath ? { subtitles_path: subtitlesPath } : {}),
        ...(title ? { title } : {}),
        ...(naming ? { naming } : {}),
      }),
    }),

  renderNames: (rule: string, collectionName: string | null, ownTitles: string[], numberDigits: number | null, signal?: AbortSignal) =>
    req<string[]>('/sources/render-names', {
      method: 'POST',
      body: JSON.stringify({ rule, collection_name: collectionName, own_titles: ownTitles, number_digits: numberDigits }),
      signal,
    }),

  describeInput: (text: string, signal?: AbortSignal) =>
    req<InputDescription>('/sources/describe-input', { method: 'POST', body: JSON.stringify({ text }), signal }),

  createTopic: (query: string, title?: string) =>
    req<{ id: number; status: string }>('/sources/topic', {
      method: 'POST',
      body: JSON.stringify({ query, ...(title ? { title } : {}) }),
    }),

  renameSource: (id: number, title: string) =>
    req<{ id: number; title: string }>(`/sources/${id}/title`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  listSources: () => req<SourceSummary[]>('/sources'),

  getReview: (scope: SetScope, sort: CandidateSortOrder = 'relevance') =>
    req<ReviewDetail>(`/api/review?${new URLSearchParams({ scope: String(scope), sort })}`),

  getReviewDocuments: (scope: SetScope) =>
    req<SourceDocument[]>(`/api/review/documents?${new URLSearchParams({ scope: String(scope) })}`),

  getReviewGeneration: (scope: SetScope) =>
    req<GenerationOverview>(`/api/review/generation?${new URLSearchParams({ scope: String(scope) })}`),

  runReviewGeneration: (scope: SetScope, kind: GenerationKind, cards: GenerationScope, sort: CandidateSortOrder = 'relevance') =>
    req<{ enqueued: number }>(
      `/api/review/generation/${kind}?${new URLSearchParams({ scope: String(scope), cards, sort })}`,
      { method: 'POST' },
    ),

  cancelReviewGeneration: (scope: SetScope, kind: GenerationKind) =>
    req<{ cancelled: number }>(`/api/review/generation/${kind}/cancel?${new URLSearchParams({ scope: String(scope) })}`, { method: 'POST' }),

  downloadReviewVideos: (scope: SetScope) =>
    req<{ queued: number }>(`/api/review/download-video?${new URLSearchParams({ scope: String(scope) })}`, { method: 'POST' }),

  processSource: (id: number) =>
    req<{ status: string }>(`/sources/${id}/process`, { method: 'POST' }),

  previewCloze: (id: number, draft: Partial<ClozeDraft>, signal?: AbortSignal) =>
    req<ClozePreview>(`/phrases/${id}/cloze/preview`, { method: 'POST', body: JSON.stringify(draft), signal }),

  saveCloze: (phraseId: number, request: SaveClozeRequest) =>
    req<StoredCandidate>(`/phrases/${phraseId}/cloze`, { method: 'PUT', body: JSON.stringify(request) }),

  decidePhrase: (phraseId: number, button: DecisionButton) =>
    req<StoredCandidate>(`/phrases/${phraseId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ button }),
    }),

  getAnkiStatus: () => req<AnkiStatus>('/anki/status'),

  getExportCards: (scope: SetScope = 'all') =>
    req<GlobalExport>(`/export/cards?${new URLSearchParams({ scope: String(scope) })}`),

  syncToAnki: (group: ExportGroup, scope: SetScope = 'all') =>
    req<SyncResult>(`/export/sync-to-anki?${new URLSearchParams({ group, scope: String(scope) })}`, { method: 'POST' }),

  getSettings: () => req<Settings>('/api/settings'),

  updateSettings: (patch: Partial<Settings>) =>
    req<Settings>('/api/settings', { method: 'PATCH', body: JSON.stringify(patch) }),

  getFrequentWordThresholds: () =>
    req<FrequentWordThresholdOption[]>('/api/settings/frequent-word-thresholds'),

  getKnownWords: () => req<KnownWord[]>('/known-words'),

  getLearningWords: () => req<LearningWords>('/vocabulary/learning'),

  deleteKnownWord: (removalKey: string) =>
    req<{ deleted: string }>(`/known-words/${encodeURIComponent(removalKey)}`, { method: 'DELETE' }),

  getUnknownWords: () => req<UnknownWord[]>('/unknown-words'),

  deleteUnknownWord: (id: number) =>
    req<{ deleted: number }>(`/unknown-words/${id}`, { method: 'DELETE' }),

  deleteSource: (id: number) => reqVoid(`/sources/${id}`, { method: 'DELETE' }),

  generateMeaning: (phraseId: number, followUpAction?: FollowUpAction, followUpText?: string) =>
    req<{ status: string }>(`/phrases/${phraseId}/generate-meaning`, {
      method: 'POST',
      body: followUpAction
        ? JSON.stringify({ action: followUpAction, ...(followUpText ? { text: followUpText } : {}) })
        : undefined,
    }),

  regeneratePhraseMedia: (phraseId: number) =>
    req<{ status: string }>(`/phrases/${phraseId}/regenerate-media`, { method: 'POST' }),

  searchTargetImages: (wordId: number, query?: string) =>
    req<ImageSearchResult>(`/words/${wordId}/image-options${query === undefined ? '' : `?${new URLSearchParams({ query })}`}`),

  applyTargetImage: (wordId: number, url: string) =>
    req<{ status: string }>(`/words/${wordId}/image`, { method: 'PUT', body: JSON.stringify({ url }) }),

  pasteTargetImage: (wordId: number, picture: Blob) =>
    req<{ status: string }>(`/words/${wordId}/image/pasted`, {
      method: 'PUT',
      headers: { 'Content-Type': picture.type, ...buildHeaders() },
      body: picture,
    }),

  polishPhraseAgain: (phraseId: number) =>
    req<{ status: string }>(`/phrases/${phraseId}/polish`, { method: 'POST' }),

  setPolishReverted: (phraseId: number, reverted: boolean) =>
    req<{ id: number; reverted: boolean }>(`/phrases/${phraseId}/polish/reverted`, {
      method: 'PUT',
      body: JSON.stringify({ reverted }),
    }),

  editPhrase: (phraseId: number, phrase: string) =>
    req<{ id: number }>(`/phrases/${phraseId}/phrase`, {
      method: 'PUT',
      body: JSON.stringify({ phrase }),
    }),

  generatePhraseTTS: (phraseId: number) =>
    req<{ status: string }>(`/phrases/${phraseId}/generate-tts`, { method: 'POST' }),

  enqueueTopicGeneration: (sourceId: number) =>
    req<{ status: string }>(`/sources/${sourceId}/topic-targets/generate`, { method: 'POST' }),

  previewRebuild: (scope: SetScope, mode: RebuildMode) =>
    req<SourceOperation>(`/api/operations/preview?${new URLSearchParams({ scope: String(scope), of: mode })}`, { method: 'POST' }),

  rebuild: (scope: SetScope, mode: RebuildMode) =>
    req<SourceOperation>(`/api/operations/${mode}?${new URLSearchParams({ scope: String(scope) })}`, { method: 'POST' }),

  refresh: (scope: SetScope) =>
    req<SourceOperation>(`/api/operations/refresh?${new URLSearchParams({ scope: String(scope) })}`, { method: 'POST' }),

  getOperation: (scope: SetScope) =>
    req<SourceOperation>(`/api/operations?${new URLSearchParams({ scope: String(scope) })}`),

  getStats: () => req<Stats>('/stats'),

  getUsage: (period: UsagePeriod, timezone: string) =>
    req<AIUsageStats>(`/api/usage?period=${period}&tz=${encodeURIComponent(timezone)}`),

  getNoteTypes: () => req<NoteTypeCheck[]>('/anki/note-types'),

  fixNoteType: (kind: NoteTypeKind) =>
    req<NoteTypeCheck>(`/anki/note-types/${kind}/fix`, { method: 'POST' }),

  setPhraseBoundary: (phraseId: number, selection: DocumentSelection) =>
    req<{ id: number; context_fragment: string }>(`/phrases/${phraseId}/phrase-boundary`, {
      method: 'PUT',
      body: JSON.stringify({ selection }),
    }),

  reportCandidate: (phraseId: number, reasons: string[], comment: string, unknownWords: number[]) =>
    req<unknown>(`/phrases/${phraseId}/report`, {
      method: 'POST',
      body: JSON.stringify({ reasons, comment, unknown_words: unknownWords }),
    }),

  getReportReasons: () => req<ReportReason[]>('/api/card-reports/reasons'),

  replaceWithExample: (phraseId: number, exampleText: string) =>
    req<StoredCandidate>(`/phrases/${phraseId}/replace-with-example`, {
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
