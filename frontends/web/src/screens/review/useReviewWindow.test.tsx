import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ReviewExpiredError } from '@/api/client'
import type { GenerationOverview, ReviewContext, ReviewUpdate, SourceDocument } from '@/api/types'
import { cardRow, header, layout, REVIEW_ID, reviewCard, reviewUpdate } from './reviewFixtures'
import { ReviewList } from './ReviewList'
import { SourceTexts } from './SourceTexts'
import { POLL_INTERVAL_MS, useReviewWindow, type ReviewWindow } from './useReviewWindow'

const SCOPE = 'source-7'
const TOTAL = 100
const card = (id: number) => reviewCard({ phrase_id: id, word_id: id })
/** Окно вокруг карточки `focus`: её строка и по строке с каждой стороны. */
const windowAround = (focus: number, changes: Partial<ReviewUpdate> = {}) => reviewUpdate({
  layout: layout([cardRow(focus - 1, focus - 1), cardRow(focus, focus), cardRow(focus + 1, focus + 1)], { total_rows: TOTAL, total_cards: TOTAL }),
  cards: [card(focus - 1), card(focus), card(focus + 1)],
  focus_id: focus,
  ...changes,
})

/** Текст источника: по слову на карточку 41 (загружена) и 90 (нет). */
const DOCUMENT = {
  source_id: 1,
  title: 'Pilot',
  blocks: [{ type: 'paragraph', lines: [{ text: 'near far' }], level: null, mode: 'flow', ordered: null, depth: null }],
  highlights: [
    { phrase_id: 41, word_id: 41, position: { block: 0, start_line: 0, start_char: 0, end_line: 0, end_char: 4 }, cefr_level: null, is_phrasal_verb: false, is_done: false },
    { phrase_id: 90, word_id: 90, position: { block: 0, start_line: 0, start_char: 5, end_line: 0, end_char: 8 }, cefr_level: null, is_phrasal_verb: false, is_done: false },
  ],
} as unknown as SourceDocument

function Probe({ onRender }: { onRender: (view: ReviewWindow) => void }) {
  const view = useReviewWindow(SCOPE, 'relevance', null)
  onRender(view)
  return (
    <>
      <ReviewList state={view.state} onLoad={view.loadRows} onToggleSection={() => {}} renderCard={c => <span data-candidate-id={c.phrase_id} />} />
      <SourceTexts documents={view.documents} done={view.done} focused={view.current} editingSourceId={null} onWordClick={id => void view.goTo(id)} onTextSelected={() => {}} />
    </>
  )
}

const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })

describe('useReviewWindow', () => {
  let host: HTMLDivElement
  let root: Root
  let latest: ReviewWindow

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    Element.prototype.scrollIntoView = () => {}
    Element.prototype.scrollTo = () => {}
    vi.spyOn(api, 'openReview').mockResolvedValue(windowAround(41))
    vi.spyOn(api, 'reviewRows').mockResolvedValue(reviewUpdate())
    vi.spyOn(api, 'reviewChanges').mockResolvedValue(reviewUpdate())
    vi.spyOn(api, 'getReviewDocuments').mockResolvedValue([DOCUMENT])
    vi.spyOn(api, 'getReviewGeneration').mockResolvedValue({ in_progress: false, kinds: [] })
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  const render = async () => {
    await act(async () => root.render(<Probe onRender={view => { latest = view }} />))
    await flush()
  }
  const gaps = () => [...host.querySelectorAll<HTMLElement>('[data-gap-start]')].map(g => `${g.dataset.gapStart}-${g.dataset.gapEnd}`)

  it('opens on the server focus with the window around it; the rows above are not fetched', async () => {
    await render()
    expect(api.openReview).toHaveBeenCalledWith({ scope: SCOPE, sort: 'relevance', requested_id: null, open_sections: [] })
    expect(latest.current?.phrase_id).toBe(41)
    expect(latest.position).toBe(42)
    expect(gaps()).toEqual(['0-40', '43-100'])
    expect(api.reviewRows).not.toHaveBeenCalled()
  })

  it('Review Focus 4: a highlight of a card not loaded opens the window around it', async () => {
    vi.spyOn(api, 'reviewAround').mockResolvedValue(windowAround(90))
    await render()

    await act(async () => { host.querySelector<HTMLElement>('[data-mark-id="90"]')!.click() })
    await flush()

    expect(vi.mocked(api.reviewAround).mock.calls).toEqual([[{ review_id: REVIEW_ID, since: 1, current: 41 }, 90]])
    expect(latest.current?.phrase_id).toBe(90)
    expect(gaps()).toEqual(['0-40', '43-89', '92-100'])
    expect(api.reviewRows).not.toHaveBeenCalled()
  })

  it('a highlight of a loaded card makes it current without a request', async () => {
    vi.spyOn(api, 'reviewAround')
    await render()
    await act(async () => { await latest.goTo(42) })
    expect(latest.current?.phrase_id).toBe(42)
    expect(api.reviewAround).not.toHaveBeenCalled()
  })

  it('Review Focus 5: an expired review opens again on the current card and the press goes once more', async () => {
    await render()
    await act(async () => { await latest.toggleSection('extra', false).catch(() => {}) })
    await act(async () => { await latest.goTo(42) })
    vi.mocked(api.openReview).mockResolvedValue(windowAround(42, { review_id: 'r2', revision: 3, focus_id: 42 }))
    const press = vi.fn(async (ctx: ReviewContext) => {
      if (ctx.review_id === REVIEW_ID) throw new ReviewExpiredError('{"detail":"review_expired"}')
      return reviewUpdate({ review_id: 'r2', revision: 4 })
    })

    await act(async () => { await latest.mutate(press) })

    expect(vi.mocked(api.openReview).mock.lastCall).toEqual([{ scope: SCOPE, sort: 'relevance', requested_id: 42, open_sections: ['extra'] }])
    expect(press.mock.calls.map(([ctx]) => ctx)).toEqual([
      { review_id: REVIEW_ID, since: 1, current: 42 },
      { review_id: 'r2', since: 3, current: 42 },
    ])
    expect(latest.state.reviewId).toBe('r2')
    expect(latest.current?.phrase_id).toBe(42)
  })

  it('a press applies the update and moves to its focus; without a focus the current stays', async () => {
    await render()
    await act(async () => {
      await latest.mutate(async () => reviewUpdate({ revision: 2, cards: [{ ...card(41), is_done: true }], done: { 41: true }, focus_id: 42 }))
    })
    expect(latest.current?.phrase_id).toBe(42)
    expect(latest.state.cards.get(41)?.is_done).toBe(true)
    expect(host.querySelector('[data-mark-id="41"]')?.className).toMatch(/markRated/)

    await act(async () => { await latest.mutate(async () => reviewUpdate({ revision: 3 })) })
    expect(latest.current?.phrase_id).toBe(42)
  })

  it('steps to the next card, fetching the rows after the current one first when they are missing', async () => {
    vi.mocked(api.reviewRows).mockResolvedValue(reviewUpdate({
      layout: layout([cardRow(43, 43), cardRow(44, 44)], { total_rows: TOTAL, total_cards: TOTAL }), cards: [card(43), card(44)],
    }))
    await render()
    await act(async () => { await latest.step(1) })
    expect(latest.current?.phrase_id).toBe(42)
    expect(api.reviewRows).not.toHaveBeenCalled()

    await act(async () => { await latest.step(1) })
    expect(vi.mocked(api.reviewRows).mock.calls).toEqual([[{ review_id: REVIEW_ID, since: 1, current: 42 }, 43, 50]])
    expect(latest.current?.phrase_id).toBe(43)
  })

  it('polls the changes while a source of the set is busy, and stops when it is free', async () => {
    vi.mocked(api.openReview).mockResolvedValue(windowAround(41, { header: header({ busy: true }) }))
    vi.mocked(api.reviewChanges).mockResolvedValue(reviewUpdate({ revision: 2, header: header({ busy: false }) }))
    await render()

    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS) })
    await flush()
    expect(api.reviewChanges).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2) })
    expect(api.reviewChanges).toHaveBeenCalledTimes(1)
  })

  it('polls the changes and the generation while generation is in progress', async () => {
    vi.mocked(api.getReviewGeneration).mockResolvedValue({ in_progress: true, kinds: [] } as GenerationOverview)
    await render()
    const reads = vi.mocked(api.getReviewGeneration).mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS) })
    await flush()
    expect(api.reviewChanges).toHaveBeenCalledTimes(1)
    expect(vi.mocked(api.getReviewGeneration).mock.calls.length).toBeGreaterThan(reads)

    vi.mocked(api.getReviewGeneration).mockResolvedValue({ in_progress: false, kinds: [] })
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS) })
    await flush()
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2) })
    expect(api.reviewChanges).toHaveBeenCalledTimes(2)
  })

  it('shows the AI-unavailable banner when an update says so', async () => {
    await render()
    expect(latest.aiBlocked).toBe(false)
    await act(async () => { await latest.mutate(async () => reviewUpdate({ revision: 2, header: header({ ai_unavailable: true }) })) })
    expect(latest.aiBlocked).toBe(true)
  })

  it('a gone set shows nothing to review', async () => {
    vi.mocked(api.openReview).mockRejectedValue(new Error('404: gone'))
    await render()
    expect(latest.gone).toBe(true)
  })
})
