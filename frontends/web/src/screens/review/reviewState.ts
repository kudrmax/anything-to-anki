import type { ReviewHeader, ReviewRow, ReviewUpdate, StoredCandidate } from '@/api/types'

/** «Разобрана» из ответа ревью и ревизия этого ответа: перечитанный позже текст её сменяет. */
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
}

/** Ответ ревью поверх того, что клиент уже знает. Устаревший ответ (меньшая ревизия) ничего не меняет. */
export function applyUpdate(state: ReviewState, update: ReviewUpdate, options: ApplyOptions = {}): ReviewState {
  if (state.reviewId !== null && update.review_id !== state.reviewId) return state
  if (update.revision < state.revision) return state
  const layout = update.layout !== null && update.layout.version >= state.version ? update.layout : null
  const replace = layout?.replace ?? false

  const removed = new Set(update.removed)
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
    for (const card of update.cards) next.set(card.phrase_id, card)
    for (const id of removed) next.delete(id)
    cards = next
  }

  const doneEntries = Object.entries(update.done)
  let done = state.done
  if (doneEntries.length > 0) {
    const next = new Map(state.done)
    for (const [id, isDone] of doneEntries) next.set(Number(id), { done: isDone, revision: update.revision })
    done = next
  }

  return {
    reviewId: update.review_id,
    revision: options.window ? state.revision : update.revision,
    header: update.header,
    version: layout?.version ?? state.version,
    totalRows: layout?.total_rows ?? state.totalRows,
    totalCards: layout?.total_cards ?? state.totalCards,
    rows,
    cards,
    done,
    currentId: update.focus_id ?? state.currentId,
  }
}

/** Ревью, открытое заново: всё прежнее уходит, кроме отметок «разобрана» для текста. */
export const reopened = (state: ReviewState, update: ReviewUpdate): ReviewState =>
  applyUpdate({ ...initialState, done: state.done }, update)

/** Текущая карточка — из загруженных строк. */
export const withCurrent = (state: ReviewState, phraseId: number): ReviewState =>
  (state.currentId === phraseId ? state : { ...state, currentId: phraseId })

/** Текст перечитан на ревизии `upTo` или позже: отметки ответов до неё он уже знает. */
export function forgetDone(state: ReviewState, upTo: number): ReviewState {
  const done = new Map([...state.done].filter(([, mark]) => mark.revision > upTo))
  return done.size === state.done.size ? state : { ...state, done }
}

/** Отметки «разобрана» из ответов — поверх отметок текста. */
export const doneMarks = (state: ReviewState): ReadonlyMap<number, boolean> =>
  new Map([...state.done].map(([id, mark]) => [id, mark.done]))

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
