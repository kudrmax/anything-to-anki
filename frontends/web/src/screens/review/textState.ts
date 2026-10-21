import type { Highlight, ReviewContents, ReviewUpdate, TextChunk, TextChunkRef } from '@/api/types'
import type { DoneMark } from './reviewState'

/** Подсветки куска и ревизия ответа, который их принёс. */
export interface HeldHighlights {
  revision: number
  highlights: readonly Highlight[]
}

/** Текст набора, что есть у клиента: оглавление, загруженные куски и их подсветки. */
export interface TextState {
  contents: ReviewContents | null
  /** Ревью, чьё это оглавление. */
  reviewId: string | null
  /** Куски по источнику, по возрастанию first_block. */
  chunks: ReadonlyMap<number, readonly TextChunk[]>
  /** По ключу `${source_id}:${first_block}`. */
  highlights: ReadonlyMap<string, HeldHighlights>
}

export const initialText: TextState = { contents: null, reviewId: null, chunks: new Map(), highlights: new Map() }

const keyOf = (sourceId: number, firstBlock: number): string => `${sourceId}:${firstBlock}`

/** Незагруженные блоки [start, end) и их размер в символах; end null — конец документа, чьих кусков ещё нет. */
export interface TextGap {
  start: number
  end: number | null
  chars: number
}

export type TextItem = { chunk: TextChunk } | { gap: TextGap }

export const isTextGap = (item: TextItem): item is { gap: TextGap } => 'gap' in item

/**
 * Ответ ревью поверх текста. Текст куска не меняется, поэтому кусок ложится всегда. Подсветки — только
 * новее по ревизии тех, что есть, даже из устаревшего ответа и даже раньше текста их куска:
 * сервер шлёт изменившиеся подсветки один раз.
 */
export function applyText(state: TextState, update: ReviewUpdate): TextState {
  const incoming: [string, Highlight[]][] = update.highlights.map(h => [keyOf(h.source_id, h.first_block), h.highlights])
  const text = update.text
  if (text) incoming.push([keyOf(text.source_id, text.first_block), text.highlights])

  let chunks = state.chunks
  if (text && !(state.chunks.get(text.source_id) ?? []).some(c => c.first_block === text.first_block)) {
    const next = new Map(state.chunks)
    next.set(text.source_id, [...(state.chunks.get(text.source_id) ?? []), text].sort((a, b) => a.first_block - b.first_block))
    chunks = next
  }

  const newer = incoming.filter(([key]) => (state.highlights.get(key)?.revision ?? -1) < update.revision)
  const highlights = newer.length === 0 ? state.highlights : new Map([
    ...state.highlights,
    ...newer.map(([key, list]): [string, HeldHighlights] => [key, { revision: update.revision, highlights: list }]),
  ])

  return chunks === state.chunks && highlights === state.highlights ? state : { ...state, chunks, highlights }
}

/** Оглавление ревью: куски и подсветки источников, которых в нём нет, уходят. */
export function withContents(state: TextState, contents: ReviewContents, reviewId: string): TextState {
  const kept = new Set(contents.documents.map(d => d.source_id))
  const sourceOf = (key: string): number => Number(key.slice(0, key.indexOf(':')))
  return {
    contents,
    reviewId,
    chunks: new Map([...state.chunks].filter(([sourceId]) => kept.has(sourceId))),
    highlights: new Map([...state.highlights].filter(([key]) => kept.has(sourceOf(key)))),
  }
}

/** Загруженные куски: их шлёт ревью, открытое заново. */
export const chunkRefs = (state: TextState): TextChunkRef[] =>
  [...state.chunks.values()].flatMap(list => list.map(c => ({ source_id: c.source_id, first_block: c.first_block })))

/** Загруженный кусок, где лежит блок. */
export const chunkHolding = (state: TextState, sourceId: number, block: number): TextChunk | undefined =>
  state.chunks.get(sourceId)?.find(c => c.first_block <= block && block < c.end_block)

/** Подсветки куска: самые новые из пришедших. */
export const chunkHighlights = (state: TextState, chunk: TextChunk): readonly Highlight[] =>
  state.highlights.get(keyOf(chunk.source_id, chunk.first_block))?.highlights ?? chunk.highlights

/** Текст источника по порядку: загруженные куски и незагруженные участки между ними. */
export function textItems(state: TextState, sourceId: number): TextItem[] {
  const chunks = state.chunks.get(sourceId) ?? []
  if (chunks.length === 0) {
    const hint = state.contents?.documents.find(d => d.source_id === sourceId)?.size_hint ?? 0
    return [{ gap: { start: 0, end: null, chars: hint } }]
  }
  const items: TextItem[] = []
  let block = 0
  let offset = 0
  for (const chunk of chunks) {
    if (chunk.first_block > block) items.push({ gap: { start: block, end: chunk.first_block, chars: chunk.start_offset - offset } })
    items.push({ chunk })
    block = chunk.end_block
    offset = chunk.end_offset
  }
  const last = chunks[chunks.length - 1]
  if (block < last.block_count) items.push({ gap: { start: block, end: last.block_count, chars: last.text_length - offset } })
  return items
}

interface MarkedDone {
  revision: number
  done: boolean
}

const doneIndex = new WeakMap<ReadonlyMap<string, HeldHighlights>, ReadonlyMap<number, MarkedDone>>()

function markedDone(state: TextState): ReadonlyMap<number, MarkedDone> {
  let index = doneIndex.get(state.highlights)
  if (!index) {
    const built = new Map<number, MarkedDone>()
    for (const held of state.highlights.values()) {
      for (const h of held.highlights) built.set(h.phrase_id, { revision: held.revision, done: h.is_done })
    }
    index = built
    doneIndex.set(state.highlights, index)
  }
  return index
}

/** «Разобрана» в тексте: более новое по ревизии из отметки ответа и подсветки куска; при равенстве — отметка. */
export function isDoneIn(state: TextState, done: ReadonlyMap<number, DoneMark>, phraseId: number): boolean {
  const mark = done.get(phraseId)
  const marked = markedDone(state).get(phraseId)
  if (!marked) return mark?.done ?? false
  if (!mark) return marked.done
  return marked.revision > mark.revision ? marked.done : mark.done
}
