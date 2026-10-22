import type {
  AIUsageStats,
  AnkiStatus,
  AnkiTemplates,
  BootstrapStatus,
  BootstrapWord,
  CandidateSection,
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
  OpenReviewRequest,
  ReviewContents,
  ReviewContext,
  ReviewUpdate,
  TextPlace,
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
  UsagePeriod,
  NoteTypeCheck,
  NoteTypeKind,
  UnknownWord,
  LevelChangeStatus,
} from './types'
import { buildHeaders, reloadIfStale } from './clientBuild'
import { ApiError, REVIEW_EXPIRED_STATUS, ReviewExpiredError } from './errors'
import { LEVEL_CHANGE_STATUS, notifyLevelChange } from './levelChangeSignal'

export { ApiError, ReviewExpiredError } from './errors'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

async function send(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...buildHeaders() },
    ...init,
  })
  reloadIfStale(res)
  if (res.status === LEVEL_CHANGE_STATUS) notifyLevelChange()
  if (!res.ok) {
    const body = await res.text()
    throw res.status === REVIEW_EXPIRED_STATUS ? new ReviewExpiredError(body) : new ApiError(res.status, body)
  }
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

/** Ревизия клиента и показанная карточка — их шлёт каждый запрос к открытому ревью. */
function reviewParams(ctx: ReviewContext): URLSearchParams {
  const params = new URLSearchParams({ since: String(ctx.since) })
  if (ctx.current !== null) params.set('current', String(ctx.current))
  return params
}

/** Путь изменения на открытом ревью: его id, ревизия клиента и показанная карточка. */
function onReview(path: string, ctx: ReviewContext): string {
  const params = reviewParams(ctx)
  params.set('review_id', ctx.review_id)
  return `${path}${path.includes('?') ? '&' : '?'}${params}`
}

/** Путь чтения открытого ревью: id ревью — в пути. */
const reviewPath = (ctx: ReviewContext, tail: string, extra: Record<string, string> = {}): string => {
  const params = reviewParams(ctx)
  for (const [key, value] of Object.entries(extra)) params.set(key, value)
  return `/api/review/${encodeURIComponent(ctx.review_id)}/${tail}?${params}`
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

  openReview: (request: OpenReviewRequest) =>
    req<ReviewUpdate>('/api/review', { method: 'POST', body: JSON.stringify(request) }),

  reviewRows: (ctx: ReviewContext, start: number, count: number) =>
    req<ReviewUpdate>(reviewPath(ctx, 'rows', { start: String(start), count: String(count) })),

  reviewAround: (ctx: ReviewContext, phraseId: number) =>
    req<ReviewUpdate>(reviewPath(ctx, `around/${phraseId}`)),

  setReviewSection: (ctx: ReviewContext, section: CandidateSection, open: boolean) =>
    req<ReviewUpdate>(reviewPath(ctx, `sections/${section}`), { method: 'PUT', body: JSON.stringify({ open }) }),

  reviewChanges: (ctx: ReviewContext) =>
    req<ReviewUpdate>(reviewPath(ctx, 'changes')),

  reviewContents: (ctx: ReviewContext) =>
    req<ReviewContents>(reviewPath(ctx, 'contents')),

  /** Кусок текста источника, где лежит блок (-1 — последний кусок) или символ по смещению. */
  reviewText: (ctx: ReviewContext, sourceId: number, place: TextPlace) =>
    req<ReviewUpdate>(reviewPath(ctx, `text/${sourceId}`, 'at' in place ? { at: String(place.at) } : { block: String(place.block) })),

  getReviewGeneration: (scope: SetScope) =>
    req<GenerationOverview>(`/api/review/generation?${new URLSearchParams({ scope: String(scope) })}`),

  runReviewGeneration: (ctx: ReviewContext, scope: SetScope, kind: GenerationKind, cards: GenerationScope, sort: CandidateSortOrder) =>
    req<ReviewUpdate>(
      onReview(`/api/review/generation/${kind}?${new URLSearchParams({ scope: String(scope), cards, sort })}`, ctx),
      { method: 'POST' },
    ),

  cancelReviewGeneration: (ctx: ReviewContext, scope: SetScope, kind: GenerationKind) =>
    req<ReviewUpdate>(onReview(`/api/review/generation/${kind}/cancel?${new URLSearchParams({ scope: String(scope) })}`, ctx), { method: 'POST' }),

  downloadReviewVideos: (ctx: ReviewContext, scope: SetScope) =>
    req<ReviewUpdate>(onReview(`/api/review/download-video?${new URLSearchParams({ scope: String(scope) })}`, ctx), { method: 'POST' }),

  processSource: (id: number) =>
    req<{ status: string }>(`/sources/${id}/process`, { method: 'POST' }),

  previewCloze: (id: number, draft: Partial<ClozeDraft>, signal?: AbortSignal) =>
    req<ClozePreview>(`/phrases/${id}/cloze/preview`, { method: 'POST', body: JSON.stringify(draft), signal }),

  saveCloze: (ctx: ReviewContext, phraseId: number, request: SaveClozeRequest) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/cloze`, ctx), { method: 'PUT', body: JSON.stringify(request) }),

  decidePhrase: (ctx: ReviewContext, phraseId: number, button: DecisionButton) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/decision`, ctx), {
      method: 'POST',
      body: JSON.stringify({ button }),
    }),

  getAnkiStatus: () => req<AnkiStatus>('/anki/status'),

  getExportCards: (scope: SetScope = 'all') =>
    req<GlobalExport>(`/export/cards?${new URLSearchParams({ scope: String(scope) })}`),

  syncToAnki: (group: ExportGroup, scope: SetScope = 'all') =>
    req<SyncResult>(`/export/sync-to-anki?${new URLSearchParams({ group, scope: String(scope) })}`, { method: 'POST' }),

  getSettings: () => req<Settings>('/api/settings'),

  getLevelChange: () => req<LevelChangeStatus>('/api/level-change'),
  cancelLevelChange: () => req<LevelChangeStatus>('/api/level-change/cancel', { method: 'POST' }),
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

  generateMeaning: (ctx: ReviewContext, phraseId: number, followUpAction?: FollowUpAction, followUpText?: string) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/generate-meaning`, ctx), {
      method: 'POST',
      body: followUpAction
        ? JSON.stringify({ action: followUpAction, ...(followUpText ? { text: followUpText } : {}) })
        : undefined,
    }),

  regeneratePhraseMedia: (ctx: ReviewContext, phraseId: number) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/regenerate-media`, ctx), { method: 'POST' }),

  searchTargetImages: (wordId: number, query?: string) =>
    req<ImageSearchResult>(`/words/${wordId}/image-options${query === undefined ? '' : `?${new URLSearchParams({ query })}`}`),

  applyTargetImage: (ctx: ReviewContext, wordId: number, url: string) =>
    req<ReviewUpdate>(onReview(`/words/${wordId}/image`, ctx), { method: 'PUT', body: JSON.stringify({ url }) }),

  pasteTargetImage: (ctx: ReviewContext, wordId: number, picture: Blob) =>
    req<ReviewUpdate>(onReview(`/words/${wordId}/image/pasted`, ctx), {
      method: 'PUT',
      headers: { 'Content-Type': picture.type, ...buildHeaders() },
      body: picture,
    }),

  polishPhraseAgain: (ctx: ReviewContext, phraseId: number) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/polish`, ctx), { method: 'POST' }),

  setPolishReverted: (ctx: ReviewContext, phraseId: number, reverted: boolean) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/polish/reverted`, ctx), {
      method: 'PUT',
      body: JSON.stringify({ reverted }),
    }),

  editPhrase: (ctx: ReviewContext, phraseId: number, phrase: string) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/phrase`, ctx), {
      method: 'PUT',
      body: JSON.stringify({ phrase }),
    }),

  generatePhraseTTS: (ctx: ReviewContext, phraseId: number) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/generate-tts`, ctx), { method: 'POST' }),

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

  setPhraseBoundary: (ctx: ReviewContext, phraseId: number, selection: DocumentSelection) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/phrase-boundary`, ctx), {
      method: 'PUT',
      body: JSON.stringify({ selection }),
    }),

  reportCandidate: (ctx: ReviewContext, phraseId: number, reasons: string[], comment: string, unknownWords: number[]) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/report`, ctx), {
      method: 'POST',
      body: JSON.stringify({ reasons, comment, unknown_words: unknownWords }),
    }),

  getReportReasons: () => req<ReportReason[]>('/api/card-reports/reasons'),

  replaceWithExample: (ctx: ReviewContext, phraseId: number, exampleText: string) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/replace-with-example`, ctx), {
      method: 'POST',
      body: JSON.stringify({ example_text: exampleText }),
    }),

  replaceWithTarget: (ctx: ReviewContext, phraseId: number) =>
    req<ReviewUpdate>(onReview(`/phrases/${phraseId}/replace-with-target`, ctx), { method: 'POST' }),

  addSavedPhrase: (phrase: string, targetWords: number[]) =>
    req<StoredCandidate>('/sources/saved-phrases', {
      method: 'POST',
      body: JSON.stringify({ phrase, target_words: targetWords }),
    }),

  addManualCandidate: (ctx: ReviewContext, sourceId: number, targetWords: number[], selection: DocumentSelection) =>
    req<ReviewUpdate>(onReview(`/sources/${sourceId}/candidates/manual`, ctx), {
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

  setCollectionFavorite: (id: number, favorite: boolean) =>
    reqVoid(`/collections/${id}/favorite`, { method: favorite ? 'PUT' : 'DELETE' }),

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
