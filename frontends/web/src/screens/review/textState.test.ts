import { describe, expect, it } from 'vitest'
import { reviewUpdate } from './reviewFixtures'
import { contents, highlight, paragraph, textChunk } from './textFixtures'
import { applyText, chunkHighlights, chunkHolding, chunkRefs, initialText, isDoneIn, textItems, withContents, type TextState } from './textState'

const opened: TextState = withContents(initialText, contents([1, 'Pilot', 5000], [2, 'Episode 2', 3000]), 'r1')
const chunk = (first: number, highlights = [highlight(41, first, 0, 4)]) =>
  textChunk(1, first, [paragraph('near text'), paragraph('more text')], highlights)

describe('applyText', () => {
  it('keeps the text of a chunk from a stale answer: text never changes', () => {
    const newer = applyText(opened, reviewUpdate({ revision: 9, highlights: [] }))
    const state = applyText(newer, reviewUpdate({ revision: 3, text: chunk(4) }))
    expect(chunkHolding(state, 1, 5)?.first_block).toBe(4)
  })

  it('takes the highlights of every answer, stale or not, newest by revision per chunk', () => {
    const fresh = [highlight(41, 4, 5, 9)]
    let state = applyText(opened, reviewUpdate({ revision: 5, highlights: [{ source_id: 1, first_block: 4, highlights: fresh }] }))
    // Старые подсветки и кусок со старыми подсветками приходят позже: подсветки остаются новыми.
    state = applyText(state, reviewUpdate({ revision: 4, highlights: [{ source_id: 1, first_block: 4, highlights: [] }] }))
    state = applyText(state, reviewUpdate({ revision: 3, text: chunk(4) }))
    expect(chunkHighlights(state, chunkHolding(state, 1, 4)!)).toEqual(fresh)

    state = applyText(state, reviewUpdate({ revision: 6, highlights: [{ source_id: 1, first_block: 4, highlights: [] }] }))
    expect(chunkHighlights(state, chunkHolding(state, 1, 4)!)).toEqual([])
  })

  it('keeps chunks sorted by their first block and lists them for a reopen', () => {
    let state = applyText(opened, reviewUpdate({ text: chunk(6) }))
    state = applyText(state, reviewUpdate({ text: chunk(0) }))
    state = applyText(state, reviewUpdate({ text: textChunk(2, 0, [paragraph('other')]) }))
    expect(chunkRefs(state)).toEqual([{ source_id: 1, first_block: 0 }, { source_id: 1, first_block: 6 }, { source_id: 2, first_block: 0 }])
  })
})

describe('withContents', () => {
  it('drops the chunks and highlights of a source that left the set', () => {
    let state = applyText(opened, reviewUpdate({ text: chunk(0) }))
    state = applyText(state, reviewUpdate({ revision: 2, text: textChunk(2, 0, [paragraph('other')], [highlight(7, 0, 0, 5)]) }))
    state = withContents(state, contents([1, 'Pilot']), 'r1')
    expect(chunkRefs(state)).toEqual([{ source_id: 1, first_block: 0 }])
    expect([...state.highlights.keys()]).toEqual(['1:0'])
  })
})

describe('textItems', () => {
  it('gives a source with no chunk one gap sized by its hint', () => {
    expect(textItems(opened, 2)).toEqual([{ gap: { start: 0, end: null, start_offset: 0, chars: 3000 } }])
  })

  it('gives the gaps around and between chunks, sized by the offsets', () => {
    let state = applyText(opened, reviewUpdate({ text: chunk(2) }))
    state = applyText(state, reviewUpdate({ text: chunk(6) }))
    const items = textItems(state, 1).map(item => ('gap' in item ? item.gap : item.chunk.first_block))
    expect(items).toEqual([
      { start: 0, end: 2, start_offset: 0, chars: 200 },
      2,
      { start: 4, end: 6, start_offset: 400, chars: 200 },
      6,
      { start: 8, end: 10, start_offset: 800, chars: 200 },
    ])
  })
})

describe('isDoneIn', () => {
  const marked = (isDone: boolean, revision: number) =>
    applyText(opened, reviewUpdate({ revision, text: textChunk(1, 0, [paragraph('near')], [highlight(41, 0, 0, 4, isDone)]) }))

  it('prefers the value with the higher revision', () => {
    expect(isDoneIn(marked(true, 5), new Map([[41, { done: false, revision: 4 }]]), 41)).toBe(true)
    expect(isDoneIn(marked(true, 5), new Map([[41, { done: false, revision: 6 }]]), 41)).toBe(false)
  })

  it('a tie goes to the done mark of the answer', () => {
    expect(isDoneIn(marked(true, 5), new Map([[41, { done: false, revision: 5 }]]), 41)).toBe(false)
  })

  it('takes whichever value there is', () => {
    expect(isDoneIn(marked(true, 5), new Map(), 41)).toBe(true)
    expect(isDoneIn(opened, new Map([[41, { done: true, revision: 1 }]]), 41)).toBe(true)
    expect(isDoneIn(opened, new Map(), 41)).toBe(false)
  })
})
