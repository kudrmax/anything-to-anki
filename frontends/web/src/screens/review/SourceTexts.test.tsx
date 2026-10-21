import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DocumentSelection, StoredCandidate } from '@/api/types'
import { reviewCard, reviewUpdate } from './reviewFixtures'
import type { SelectedText } from './SourceText'
import { TEXT_PX_PER_CHAR } from './SourceText'
import { SourceTexts } from './SourceTexts'
import { contents, listItem, paragraph, textChunk } from './textFixtures'
import { applyText, initialText, withContents, type TextState } from './textState'

const noop = () => {}

const opened = (...documents: [number, string, number?][]): TextState => withContents(initialText, contents(...documents), 'r1')
const withChunks = (state: TextState, ...chunks: ReturnType<typeof textChunk>[]): TextState =>
  chunks.reduce((s, text) => applyText(s, reviewUpdate({ text })), state)

/** Набор из двух источников, у каждого загружен первый кусок. */
const twoTexts = (): TextState => withChunks(
  opened([2, 'Episode 2'], [1, 'Pilot']),
  textChunk(2, 0, [paragraph('Text of Episode 2.')], [], 1),
  textChunk(1, 0, [paragraph('Text of Pilot.')], [], 1),
)

/** IntersectionObserver, у которого видно всё, за чем он смотрит. */
class SeeingObserver {
  static observed: HTMLElement[] = []
  /** Где заглушка относительно экрана [0, 500): по умолчанию — ниже его верха. */
  static rectOf: (gap: HTMLElement) => { top: number; bottom: number } = () => ({ top: 100, bottom: 900 })
  private readonly callback: IntersectionObserverCallback
  constructor(callback: IntersectionObserverCallback) { this.callback = callback }
  observe(element: HTMLElement) {
    SeeingObserver.observed.push(element)
    const entry = { isIntersecting: true, target: element, boundingClientRect: SeeingObserver.rectOf(element), rootBounds: { top: 0, bottom: 500 } }
    this.callback([entry as unknown as IntersectionObserverEntry], this as unknown as IntersectionObserver)
  }
  disconnect() {}
}

describe('SourceTexts', () => {
  let host: HTMLDivElement
  let root: Root
  let scrolls: ScrollToOptions[]
  let onLoad: ReturnType<typeof vi.fn<(sourceId: number, block: number) => Promise<boolean>>>
  let ensureBlock: ReturnType<typeof vi.fn<(sourceId: number, block: number) => Promise<boolean>>>
  let selected: SelectedText[]

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    scrolls = []
    Element.prototype.scrollTo = function (options?: ScrollToOptions | number) { if (typeof options === 'object') scrolls.push(options) } as typeof Element.prototype.scrollTo
    onLoad = vi.fn(async () => true)
    ensureBlock = vi.fn(async () => true)
    selected = []
    SeeingObserver.observed = []
    SeeingObserver.rectOf = () => ({ top: 100, bottom: 900 })
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
    vi.unstubAllGlobals()
  })

  const render = (text: TextState, editingSourceId: number | null = null, focused: StoredCandidate | null = null) => act(() => root.render(
    <SourceTexts
      text={text}
      done={new Map()}
      focused={focused}
      editingSourceId={editingSourceId}
      onLoad={onLoad}
      ensureBlock={ensureBlock}
      onWordClick={noop}
      onTextSelected={s => { selected.push(s) }}
    />,
  ))
  const titles = () => [...host.querySelectorAll('h3')].map(h => h.textContent)
  const selectableTitles = () =>
    [...host.querySelectorAll('[data-selectable]')].map(section => section.querySelector('h3')?.textContent)
  const placeholders = () => [...host.querySelectorAll<HTMLElement>('[data-text-gap]')]
    .map(gap => `${gap.dataset.sourceId}:${gap.dataset.gapStart}-${gap.dataset.gapEnd ?? 'end'}:${gap.style.getPropertyValue('--placeholder-h')}`)

  it('stacks every source text under its title, in contents order', () => {
    render(twoTexts())
    expect(titles()).toEqual(['Episode 2', 'Pilot'])
    expect(host.textContent).toContain('Text of Pilot.')
  })

  it('takes selections in every text while nothing is edited', () => {
    render(twoTexts())
    expect(selectableTitles()).toEqual(['Episode 2', 'Pilot'])
  })

  it('while a boundary is edited, only that source takes selections', () => {
    render(twoTexts(), 1)
    expect(selectableTitles()).toEqual(['Pilot'])
  })

  const toggle = (title: string) => {
    const button = [...host.querySelectorAll('h3 button')].find(b => b.textContent?.includes(title))
    act(() => (button as HTMLButtonElement).click())
  }

  it('folds a source text to its title and unfolds it back', () => {
    render(twoTexts())
    toggle('Pilot')
    expect(host.textContent).not.toContain('Text of Pilot.')
    expect(host.textContent).toContain('Text of Episode 2.')
    expect(host.querySelector('[data-source-id="1"] button')?.getAttribute('aria-expanded')).toBe('false')
    toggle('Pilot')
    expect(host.textContent).toContain('Text of Pilot.')
  })

  it('a single source has nothing to fold', () => {
    render(withChunks(opened([1, 'Pilot']), textChunk(1, 0, [paragraph('Text of Pilot.')], [], 1)))
    expect(host.querySelector('h3 button')).toBeNull()
    expect(titles()).toEqual(['Pilot'])
  })

  it('stands a placeholder for every range not loaded, as tall as its characters', () => {
    const px = (chars: number) => `${Math.round(chars * TEXT_PX_PER_CHAR)}px`
    render(withChunks(opened([1, 'Pilot'], [2, 'Episode 2', 3000]), textChunk(1, 2, [paragraph('a'), paragraph('b')]), textChunk(1, 6, [paragraph('c')])))
    expect(placeholders()).toEqual([
      `1:0-2:${px(200)}`, `1:4-6:${px(200)}`, `1:7-10:${px(300)}`, `2:0-end:${px(3000)}`,
    ])
  })

  it('a placeholder near the screen loads from its edge facing the screen', () => {
    vi.stubGlobal('IntersectionObserver', SeeingObserver)
    // Заглушки Pilot выше экрана, у Episode 2 — ниже.
    SeeingObserver.rectOf = gap => (gap.dataset.sourceId === '1' ? { top: -300, bottom: -10 } : { top: 600, bottom: 900 })
    render(withChunks(opened([1, 'Pilot'], [2, 'Episode 2']), textChunk(1, 2, [paragraph('a'), paragraph('b')])))
    expect(onLoad.mock.calls).toEqual([[1, 1], [1, 9], [2, 0]])

    onLoad.mockClear()
    SeeingObserver.rectOf = () => ({ top: -300, bottom: -10 })
    render(opened([1, 'Pilot'], [2, 'Episode 2']))
    // Выше экрана документ без кусков грузится с последнего.
    expect(onLoad.mock.calls).toContainEqual([2, -1])
  })

  it('numbers list items by the number the server gives, across a chunk border', () => {
    render(withChunks(
      opened([1, 'Pilot']),
      textChunk(1, 0, [listItem('one', 1), listItem('two', 2)]),
      textChunk(1, 2, [listItem('three', 3), listItem('dot', null, false)]),
    ))
    expect([...host.querySelectorAll('[aria-hidden]')].map(m => m.textContent).filter(Boolean)).toEqual(['1.', '2.', '3.', '•'])
  })

  it('a selection from a block of one chunk to a block of the next reports both absolute blocks', () => {
    Range.prototype.getBoundingClientRect = () => ({ left: 0, top: 0, bottom: 0 }) as DOMRect
    render(withChunks(opened([1, 'Pilot']), textChunk(1, 0, [paragraph('first block')]), textChunk(1, 1, [paragraph('second block')])))
    const first = host.querySelector('[data-block="0"]')!.firstChild!
    const second = host.querySelector('[data-block="1"]')!.firstChild!
    const range = document.createRange()
    range.setStart(first, 6)
    range.setEnd(second, 6)
    window.getSelection()!.removeAllRanges()
    window.getSelection()!.addRange(range)

    act(() => { host.querySelector('[data-text-block="0"]')!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })) })

    expect(selected.map(s => s.selection)).toEqual([{
      start_block: 0, start_line: 0, start_char: 6, end_block: 1, end_line: 0, end_char: 6,
    } satisfies DocumentSelection])
  })

  it('editing a far phrase unfolds its document, loads its chunk and scrolls to it', async () => {
    const far = reviewCard({ phrase_id: 9, source: { id: 1, has_video: false, can_polish_phrases: false }, phrase_position: { block: 50, start_line: 0, start_char: 0, end_line: 0, end_char: 4 } })
    let text = twoTexts()
    render(text)
    toggle('Pilot')

    await act(async () => { render(text, 1, far) })
    expect(ensureBlock.mock.calls).toEqual([[1, 50]])
    expect(scrolls).toEqual([])

    text = withChunks(text, textChunk(1, 50, [paragraph('far away')], [{ phrase_id: 9, word_id: 9, position: far.phrase_position!, cefr_level: null, is_phrasal_verb: false, is_done: false }], 60))
    await act(async () => { render(text, 1, far) })
    expect(host.textContent).toContain('far away')
    expect(scrolls.map(s => s.behavior)).toEqual(['auto'])
  })

  it('editing an example (no place) leaves the text where it is', async () => {
    const example = reviewCard({ phrase_id: 9, source: { id: 1, has_video: false, can_polish_phrases: false }, phrase_position: null })
    render(twoTexts())
    await act(async () => { render(twoTexts(), 1, example) })
    expect(ensureBlock).not.toHaveBeenCalled()
    expect(scrolls).toEqual([])
  })

  it('a folded document requests nothing, even for the current card in it', async () => {
    vi.stubGlobal('IntersectionObserver', SeeingObserver)
    const text = withChunks(opened([2, 'Episode 2'], [1, 'Pilot']), textChunk(2, 0, [paragraph('Text of Episode 2.')], [], 1))
    render(text)
    toggle('Pilot')
    onLoad.mockClear()
    SeeingObserver.observed = []
    const inPilot = reviewCard({ phrase_id: 9, phrase_position: { block: 5, start_line: 0, start_char: 0, end_line: 0, end_char: 4 } })

    await act(async () => { render(withChunks(text, textChunk(2, 1, [paragraph('more')], [], 3)), null, inPilot) })

    expect(onLoad.mock.calls.every(([sourceId]) => sourceId === 2)).toBe(true)
    expect(SeeingObserver.observed.every(gap => gap.dataset.sourceId === '2')).toBe(true)
    expect(ensureBlock).not.toHaveBeenCalled()
  })
})
