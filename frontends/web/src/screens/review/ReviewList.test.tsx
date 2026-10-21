import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cardRow, layout, reviewCard, reviewUpdate, sectionRow } from './reviewFixtures'
import { ReviewList } from './ReviewList'
import { applyUpdate, fetchStart, initialState, withCurrent } from './reviewState'
import { ROW_ESTIMATE_PX, ROWS_PER_FETCH } from './useReviewWindow'

const rect = (top: number, bottom: number) => ({ top, bottom, height: bottom - top }) as DOMRectReadOnly
const VIEW = { top: 0, bottom: 1000 }

describe('fetchStart', () => {
  it('loads from the top edge down when the top edge is near the screen', () => {
    expect(fetchStart(100, 400, rect(500, 500 + 300 * ROW_ESTIMATE_PX), VIEW, ROWS_PER_FETCH)).toBe(100)
  })

  it('loads up to the bottom edge when the bottom edge is near the screen', () => {
    expect(fetchStart(0, 300, rect(-300 * ROW_ESTIMATE_PX + 200, 200), VIEW, ROWS_PER_FETCH)).toBe(250)
  })

  it('loads the rows on the screen when the middle of a long gap shows', () => {
    expect(fetchStart(0, 1000, rect(-100 * ROW_ESTIMATE_PX, 900 * ROW_ESTIMATE_PX), VIEW, ROWS_PER_FETCH)).toBe(100)
  })
})

describe('ReviewList', () => {
  let host: HTMLDivElement
  let root: Root
  let observed: Element[]
  let fire: (target: Element, bounds: DOMRectReadOnly) => void

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    Element.prototype.scrollIntoView = () => {}
    observed = []
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: IntersectionObserverCallback) {
        fire = (target, bounds) => callback([{ target, isIntersecting: true, boundingClientRect: bounds, rootBounds: VIEW } as unknown as IntersectionObserverEntry], this as unknown as IntersectionObserver)
      }
      observe(target: Element) { observed.push(target) }
      disconnect() { observed = [] }
    })
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.unstubAllGlobals()
  })

  const state = withCurrent(applyUpdate(initialState, reviewUpdate({
    layout: layout([cardRow(200, 1), sectionRow(201, 'extra', 4)], { total_rows: 400, total_cards: 399 }),
    cards: [reviewCard({ phrase_id: 1 })],
  })), 1)

  it('renders loaded rows and one placeholder per run of rows not loaded, and loads each from its edge', async () => {
    const onLoad = vi.fn(async () => true)
    await act(async () => root.render(
      <ReviewList state={state} onLoad={onLoad} onToggleSection={() => {}} renderCard={c => <span data-candidate-id={c.phrase_id} />} />,
    ))
    expect(host.textContent).toContain('Show 4 phrases with more new words')
    expect(observed.map(gap => (gap as HTMLElement).dataset.gapStart)).toEqual(['0', '202'])

    await act(async () => fire(observed[0], rect(-200 * ROW_ESTIMATE_PX + 100, 100)))
    await act(async () => fire(observed[1], rect(900, 900 + 198 * ROW_ESTIMATE_PX)))
    expect(onLoad.mock.calls).toEqual([[150, 50], [202, 50]])
  })
})
