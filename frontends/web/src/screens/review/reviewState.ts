import type { ReviewHeader, ReviewRow, ReviewUpdate, StoredCandidate } from '@/api/types'

/** «Разобрана» из ответа ревью и ревизия этого ответа: подсветка куска новее по ревизии её сменяет. */
export interface DoneMark {
  done: boolean
  revision: number
}

/** То, что клиент знает об открытом ревью: загруженные строки видимого списка и их карточки. */
export interface ReviewState {
  reviewId: string | null
  /** Ревизия, до которой клиент знает все изменения: её он шлёт как since. */
  revision: number
  header: ReviewHeader | null
  version: number
  totalRows: number
  totalCards: number
  /** Загруженные строки по номеру; номера без строки — ещё не загружены. */
  rows: ReadonlyMap<number, ReviewRow>
  cards: ReadonlyMap<number, StoredCandidate>
  done: ReadonlyMap<number, DoneMark>
  currentId: number | null
}

export const initialState: ReviewState = {
  reviewId: null,
  revision: 0,
  header: null,
  version: 0,
  totalRows: 0,
  totalCards: 0,
  rows: new Map(),
  cards: new Map(),
  done: new Map(),
  currentId: null,
}

export interface ApplyOptions {
  /**
   * Ответ чтения окна (строки, окно вокруг карточки, раздел): его карточки свежие, но изменений
   * с since в нём нет, поэтому ревизия клиента остаётся прежней — их принесёт следующий ответ.
   */
  window?: boolean
  /** Экран уже перешёл сам (нажатие показано до ответа): фокус ответа не ложится, его решает вызывающий. */
  keepCurrent?: boolean
}

/**
 * Раскладка новее той, что у клиента, но пришла без replace: ответ с replace потерялся
 * (его обогнал опрос или он не дошёл). Клиент её примет как новую и запросит окно вокруг текущей.
 */
export const missesReplace = (state: ReviewState, update: ReviewUpdate): boolean =>
  (state.reviewId === null || update.review_id === state.reviewId)
  && update.layout !== null && !update.layout.replace && update.layout.version > state.version

/**
 * Ответ ревью поверх того, что клиент уже знает. Устаревший ответ (меньшая ревизия) ничего не меняет,
 * кроме раскладки новой версии: её строки ложатся всегда, иначе номера строк двух раскладок смешаются.
 */
export function applyUpdate(state: ReviewState, update: ReviewUpdate, options: ApplyOptions = {}): ReviewState {
  if (state.reviewId !== null && update.review_id !== state.reviewId) return state
  const stale = update.revision < state.revision
  const incoming = update.layout
  const newer = incoming !== null && incoming.version > state.version
  const layout = incoming !== null && (newer || (!stale && incoming.version === state.version)) ? incoming : null
  if (stale && layout === null) return state
  // Раскладка новой версии без replace — значит, replace пропущен: прежние строки ей не принадлежат.
  const replace = layout !== null && (layout.replace || newer)

  const removed = new Set(stale ? [] : update.removed)
  // Без изменений карта остаётся той же: по ней кэшируются номера строк.
  let rows = state.rows
  if (layout !== null || removed.size > 0) {
    const next = new Map(replace ? [] : state.rows)
    for (const row of layout?.rows ?? []) next.set(row.index, row)
    for (const [index, row] of next) if (row.phrase_id !== null && removed.has(row.phrase_id)) next.delete(index)
    rows = next
  }
  let cards = state.cards
  if (replace || update.cards.length > 0 || removed.size > 0) {
    const next = new Map(replace ? [] : state.cards)
    for (const card of update.cards) {
      // У устаревшего ответа карточка старше той, что у клиента: берём его только за неимением своей.
      const own = state.cards.get(card.phrase_id)
      next.set(card.phrase_id, stale && own ? own : card)
    }
    for (const id of removed) next.delete(id)
    cards = next
  }

  const doneEntries = stale ? [] : Object.entries(update.done)
  let done = state.done
  if (doneEntries.length > 0) {
    const next = new Map(state.done)
    for (const [id, isDone] of doneEntries) next.set(Number(id), { done: isDone, revision: update.revision })
    done = next
  }

  return {
    reviewId: update.review_id,
    revision: options.window || stale ? state.revision : update.revision,
    header: stale ? state.header : update.header,
    version: layout?.version ?? state.version,
    totalRows: layout?.total_rows ?? state.totalRows,
    totalCards: layout?.total_cards ?? state.totalCards,
    rows,
    cards,
    done,
    currentId: stale || options.keepCurrent ? state.currentId : update.focus_id ?? state.currentId,
  }
}

/** Ревью, открытое заново: всё прежнее уходит, кроме отметок «разобрана» для текста. */
export const reopened = (state: ReviewState, update: ReviewUpdate): ReviewState =>
  applyUpdate({ ...initialState, done: state.done }, update)

/** Текущая карточка — из загруженных строк. */
export const withCurrent = (state: ReviewState, phraseId: number): ReviewState =>
  (state.currentId === phraseId ? state : { ...state, currentId: phraseId })

const indexCache = new WeakMap<ReadonlyMap<number, ReviewRow>, ReadonlyMap<number, number>>()

/** Номер загруженной строки карточки; undefined — её строка не загружена. */
export function rowIndexOf(state: ReviewState, phraseId: number | null): number | undefined {
  if (phraseId === null) return undefined
  let index = indexCache.get(state.rows)
  if (!index) {
    index = new Map([...state.rows].flatMap(([i, row]) => (row.phrase_id === null ? [] : [[row.phrase_id, i] as const])))
    indexCache.set(state.rows, index)
  }
  return index.get(phraseId)
}

/** Загружены ли все строки между двумя номерами (включительно). */
export function rowsLoaded(state: ReviewState, from: number, to: number): boolean {
  for (let i = Math.min(from, to); i <= Math.max(from, to); i++) if (!state.rows.has(i)) return false
  return true
}

/** Строка текущей карточки: её позиция в видимом списке. */
export const currentRow = (state: ReviewState): ReviewRow | null => {
  const index = rowIndexOf(state, state.currentId)
  return index === undefined ? null : state.rows.get(index) ?? null
}

/**
 * Карточка на позиции `position ± 1` от текущей, если её строка загружена. `null` — такой позиции нет;
 * `undefined` — строки между ними ещё не загружены.
 */
export function neighbour(state: ReviewState, delta: 1 | -1): number | null | undefined {
  const index = rowIndexOf(state, state.currentId)
  const row = index === undefined ? undefined : state.rows.get(index)
  if (index === undefined || !row || row.position === null) return null
  const target = row.position + delta
  if (target < 1 || target > state.totalCards) return null
  for (let i = index + delta; i >= 0 && i < state.totalRows; i += delta) {
    const next = state.rows.get(i)
    if (!next) return undefined
    if (next.position === target) return next.phrase_id
  }
  return null
}

/** Подряд идущие незагруженные строки: [start, end). */
export interface Gap {
  start: number
  end: number
}

/** Строки списка по порядку: загруженные — как есть, каждый незагруженный участок — одним промежутком. */
export function listRows(state: ReviewState): (ReviewRow | Gap)[] {
  const items: (ReviewRow | Gap)[] = []
  const loaded = [...state.rows.keys()].filter(i => i < state.totalRows).sort((a, b) => a - b)
  let next = 0
  for (const index of loaded) {
    if (index > next) items.push({ start: next, end: index })
    items.push(state.rows.get(index)!)
    next = index + 1
  }
  if (next < state.totalRows) items.push({ start: next, end: state.totalRows })
  return items
}

export const isGap = (item: ReviewRow | Gap): item is Gap => 'end' in item

/** С какой строки грузить заглушку [start, end): от края, что у экрана, к нему; середина — с верха экрана. */
export function fetchStart(
  start: number, end: number, rect: DOMRectReadOnly, view: { top: number; bottom: number }, rowsPerFetch: number,
): number {
  const last = Math.max(start, end - rowsPerFetch)
  if (rect.top >= view.top) return start
  if (rect.bottom <= view.bottom) return last
  const rowHeight = rect.height / (end - start)
  return Math.min(last, start + Math.floor((view.top - rect.top) / rowHeight))
}
