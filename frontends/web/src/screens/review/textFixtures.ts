import type { DocumentBlock, Highlight, ReviewContents, TextChunk } from '@/api/types'

export const paragraph = (text: string): DocumentBlock =>
  ({ type: 'paragraph', lines: [{ text }], level: null, mode: 'flow', ordered: null, depth: null, number: null })

/** Блок построчного текста — песни или субтитров: строки разделены переносом. */
export const lines = (...texts: string[]): DocumentBlock =>
  ({ type: 'paragraph', lines: texts.map(text => ({ text })), level: null, mode: 'lines', ordered: null, depth: null, number: null })

export const listItem = (text: string, number: number | null, ordered = true): DocumentBlock =>
  ({ type: 'list_item', lines: [{ text }], level: null, mode: 'flow', ordered, depth: 0, number })

/** Подсветка слова `[start, end)` в первой строке блока. */
export const highlight = (phraseId: number, block: number, start: number, end: number, isDone = false): Highlight => ({
  phrase_id: phraseId, word_id: phraseId,
  position: { block, start_line: 0, start_char: start, end_line: 0, end_char: end },
  cefr_level: null, is_phrasal_verb: false, is_done: isDone,
})

/** Кусок из блоков подряд с `firstBlock`; смещения — по 100 символов на блок. */
export const textChunk = (
  sourceId: number, firstBlock: number, blocks: DocumentBlock[], highlights: Highlight[] = [], blockCount = 10,
): TextChunk => ({
  source_id: sourceId,
  first_block: firstBlock,
  end_block: firstBlock + blocks.length,
  block_count: blockCount,
  start_offset: firstBlock * 100,
  end_offset: (firstBlock + blocks.length) * 100,
  text_length: blockCount * 100,
  blocks,
  highlights,
})

export const contents = (...documents: [number, string, number?][]): ReviewContents => ({
  version: 0,
  documents: documents.map(([sourceId, title, sizeHint]) => ({ source_id: sourceId, title, size_hint: sizeHint ?? 1000 })),
})
