import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ReviewExpiredError } from '@/api/client'
import type { GenerationOverview, ReviewContext, ReviewUpdate } from '@/api/types'
import { cardRow, header, layout, REVIEW_ID, reviewCard, reviewUpdate, sectionRow } from './reviewFixtures'
import { ReviewList } from './ReviewList'
import { SourceTexts } from './SourceTexts'
import { contents, highlight, paragraph, textChunk } from './textFixtures'
import { POLL_INTERVAL_MS, useReviewWindow, type ReviewWindow } from './useReviewWindow'

const SCOPE = 'source-7'
const TOTAL = 100
/** Фразы карточек 41 и 90 — в блоке 40 источника 1. */
const TEXT_BLOCK = 40
const card = (id: number) => reviewCard({
  phrase_id: id, word_id: id,
  phrase_position: id === 41 || id === 90 ? { block: TEXT_BLOCK, start_line: 0, start_char: 0, end_line: 0, end_char: 8 } : null,
})
/** Окно вокруг карточки `focus`: её строка и по строке с каждой стороны. */
const windowAround = (focus: number, changes: Partial<ReviewUpdate> = {}) => reviewUpdate({
  layout: layout([cardRow(focus - 1, focus - 1), cardRow(focus, focus), cardRow(focus + 1, focus + 1)], { total_rows: TOTAL, total_cards: TOTAL }),
  cards: [card(focus - 1), card(focus), card(focus + 1)],
  focus_id: focus,
  ...changes,
})

/** Кусок текста: по слову на карточку 41 (загружена) и 90 (нет). */
const CHUNK = textChunk(1, TEXT_BLOCK, [paragraph('near far')], [highlight(41, TEXT_BLOCK, 0, 4), highlight(90, TEXT_BLOCK, 5, 8)], 100)

function Probe({ onRender }: { onRender: (view: ReviewWindow) => void }) {
  const view = useReviewWindow(SCOPE, 'relevance', null)
  onRender(view)
  return (
    <>
      <ReviewList state={view.state} onLoad={view.loadRows} onToggleSection={() => {}} renderCard={c => <span data-candidate-id={c.phrase_id} />} />
      <SourceTexts
        text={view.text} done={view.state.done} focused={view.current} editingSourceId={null}
        onLoad={view.loadText} ensureBlock={view.ensureBlock} onWordClick={id => void view.goTo(id)} onTextSelected={() => {}}
      />
    </>
  )
}

const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })

describe('useReviewWindow', () => {
  let host: HTMLDivElement
  let root: Root
  let latest: ReviewWindow
  let scrolls: string[]

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    scrolls = []
    Element.prototype.scrollIntoView = function (this: Element, options?: boolean | ScrollIntoViewOptions) {
      scrolls.push(`${(this as HTMLElement).dataset.candidateId}:${typeof options === 'object' ? options.behavior : ''}`)
    }
    Element.prototype.scrollTo = () => {}
    vi.spyOn(api, 'openReview').mockResolvedValue(windowAround(41))
    vi.spyOn(api, 'reviewRows').mockResolvedValue(reviewUpdate())
    vi.spyOn(api, 'reviewChanges').mockResolvedValue(reviewUpdate())
    vi.spyOn(api, 'reviewContents').mockResolvedValue(contents([1, 'Pilot', 50_000]))
    vi.spyOn(api, 'reviewText').mockResolvedValue(reviewUpdate({ text: CHUNK }))
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
  const gaps = () => [...host.querySelectorAll<HTMLElement>('[data-gap-start]:not([data-text-gap])')].map(g => `${g.dataset.gapStart}-${g.dataset.gapEnd}`)

  it('opens on the server focus with the window around it; the rows above are not fetched', async () => {
    await render()
    expect(api.openReview).toHaveBeenCalledWith({ scope: SCOPE, sort: 'relevance', requested_id: null, open_sections: [], text_chunks: [] })
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

  it('tells the server when the current card leaves a section it opened, and takes the folded list', async () => {
    // 41 открыта ссылкой в свёрнутом Extra: сервер раскрыл раздел сам. 40 — последняя в Ready.
    vi.mocked(api.openReview).mockResolvedValue(reviewUpdate({
      layout: layout([cardRow(0, 40, 1), sectionRow(1, 'extra', 2, true), cardRow(2, 41, 2), cardRow(3, 42, 3)], { replace: true }),
      cards: [card(40), card(41), card(42)],
      focus_id: 41,
    }))
    vi.mocked(api.reviewChanges).mockResolvedValue(reviewUpdate({
      revision: 2, layout: layout([cardRow(0, 40, 1), sectionRow(1, 'extra', 2, false)], { version: 1, replace: true }), cards: [card(40)],
    }))
    await render()

    await act(async () => { await latest.goTo(40) })
    expect(latest.current?.phrase_id).toBe(40)
    expect(api.reviewChanges).not.toHaveBeenCalled()
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 300)) })

    expect(vi.mocked(api.reviewChanges).mock.calls).toEqual([[{ review_id: REVIEW_ID, since: 1, current: 40 }]])
    expect(host.textContent).toContain('Show 2 phrases with more new words')
    expect(latest.state.totalRows).toBe(2)
  })

  it('a newer list that comes without replace asks for the window around the current card', async () => {
    vi.spyOn(api, 'reviewAround').mockResolvedValue(windowAround(41, { revision: 2, layout: layout([cardRow(40, 40), cardRow(41, 41), cardRow(42, 42)], { version: 1, total_rows: TOTAL, total_cards: TOTAL }) }))
    await render()
    await act(async () => {
      await latest.mutate(async () => reviewUpdate({ revision: 2, layout: layout([cardRow(41, 41)], { version: 1, total_rows: TOTAL, total_cards: TOTAL }), cards: [card(41)] }))
    })
    await flush()
    expect(vi.mocked(api.reviewAround).mock.calls).toEqual([[{ review_id: REVIEW_ID, since: 2, current: 41 }, 41]])
    expect([...latest.state.rows.keys()].sort()).toEqual([40, 41, 42])
  })

  it('a step asks for the rows once more when their first answer came stale', async () => {
    await render()
    await act(async () => { await latest.mutate(async () => reviewUpdate({ revision: 3, focus_id: 42 })) })
    vi.mocked(api.reviewRows)
      .mockResolvedValueOnce(reviewUpdate({ revision: 2, layout: layout([cardRow(43, 43)], { total_rows: TOTAL, total_cards: TOTAL }), cards: [card(43)] }))
      .mockResolvedValueOnce(reviewUpdate({ revision: 3, layout: layout([cardRow(43, 43)], { total_rows: TOTAL, total_cards: TOTAL }), cards: [card(43)] }))
    await act(async () => { await latest.step(1) })
    expect(api.reviewRows).toHaveBeenCalledTimes(2)
    expect(latest.current?.phrase_id).toBe(43)
  })

  it('steps pressed while rows load land one after another, not on the same card', async () => {
    vi.mocked(api.reviewRows).mockImplementation(async () => reviewUpdate({
      layout: layout([cardRow(43, 43), cardRow(44, 44)], { total_rows: TOTAL, total_cards: TOTAL }), cards: [card(43), card(44)],
    }))
    await render()
    await act(async () => { await latest.goTo(42) })
    await act(async () => { await Promise.all([latest.step(1), latest.step(1)]) })
    expect(latest.current?.phrase_id).toBe(44)
  })

  it('jumps to the card at once on opening and on a far jump, and loads no rows on the way', async () => {
    vi.spyOn(api, 'reviewAround').mockResolvedValue(windowAround(90))
    await render()
    expect(scrolls).toEqual(['41:auto'])

    await act(async () => { await latest.goTo(90) })
    await flush()
    expect(scrolls.at(-1)).toBe('90:auto')
    expect(api.reviewRows).not.toHaveBeenCalled()
  })

  it('scrolls smoothly to a neighbour over loaded rows', async () => {
    await render()
    await act(async () => { await latest.step(1) })
    expect(scrolls.at(-1)).toBe('42:smooth')
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

    expect(vi.mocked(api.openReview).mock.lastCall).toEqual([{ scope: SCOPE, sort: 'relevance', requested_id: 42, open_sections: ['extra'], text_chunks: [{ source_id: 1, first_block: TEXT_BLOCK }] }])
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

  /** Ответ, который придёт, когда тест скажет. */
  const deferred = () => {
    let resolve: (update: ReviewUpdate) => void = () => {}
    let reject: (e: Error) => void = () => {}
    const promise = new Promise<ReviewUpdate>((ok, fail) => { resolve = ok; reject = fail })
    return { promise, resolve, reject }
  }

  it('#18: a press moves to the next card before its answer; the presses go to the server one after another', async () => {
    await render()
    const first = deferred()
    const second = deferred()
    const calls: ReviewContext[] = []
    let running: Promise<unknown> = Promise.resolve()
    act(() => {
      running = latest.mutate(ctx => { calls.push(ctx); return first.promise }, { phraseId: 41, closes: 'card' })
    })
    expect(latest.current?.phrase_id).toBe(42)
    expect(latest.state.done.get(41)?.done).toBe(true)

    let next: Promise<unknown> = Promise.resolve()
    act(() => {
      next = latest.mutate(ctx => { calls.push(ctx); return second.promise }, { phraseId: 42, closes: 'card' })
    })
    await flush()
    expect(calls).toHaveLength(1)

    await act(async () => {
      first.resolve(reviewUpdate({ revision: 2, done: { 41: true }, focus_id: 42 }))
      await running
    })
    await flush()
    expect(calls).toHaveLength(2)
    // Экран ушёл дальше: фокус первого ответа его не тянет назад.
    expect(latest.state.currentId).toBe(42)
    await act(async () => {
      second.resolve(reviewUpdate({ revision: 3, done: { 42: true }, focus_id: 43 }))
      await next
    })
    expect(latest.state.currentId).toBe(43)
  })

  it('#18: the answer moves the focus where the server put it when the screen guessed otherwise', async () => {
    await render()
    await act(async () => {
      await latest.mutate(async () => reviewUpdate({
        revision: 2, done: { 41: true, 42: true }, focus_id: 90,
        layout: layout([cardRow(89, 90)], { total_rows: TOTAL, total_cards: TOTAL }), cards: [card(90)],
      }), { phraseId: 41, closes: 'card' })
    })
    expect(latest.state.currentId).toBe(90)
  })

  it('#24: a new list without the current card keeps the card on screen and asks for the rows around it', async () => {
    await render()
    const around = deferred()
    vi.spyOn(api, 'reviewAround').mockReturnValue(around.promise)
    const answer = deferred()
    let running: Promise<unknown> = Promise.resolve()
    act(() => { running = latest.mutate(() => answer.promise, { phraseId: 41, closes: 'card' }) })
    expect(latest.state.currentId).toBe(42)

    await act(async () => {
      answer.resolve(reviewUpdate({
        revision: 2, done: { 41: true }, focus_id: 42,
        layout: layout([cardRow(0, 7), cardRow(1, 8)], { version: 1, total_rows: TOTAL, total_cards: TOTAL, replace: true }),
        cards: [card(7), card(8)],
      }))
      await running
    })
    expect(latest.current?.phrase_id).toBe(42)
    await flush()
    expect(vi.mocked(api.reviewAround).mock.calls.map(([, id]) => id)).toEqual([42])

    // Пока строки шли, экран ушёл дальше: их ответ его не возвращает.
    await act(async () => { await latest.mutate(async () => reviewUpdate({ revision: 3, focus_id: 8 })) })
    expect(latest.state.currentId).toBe(8)
    await act(async () => { around.resolve(windowAround(42, { revision: 3 })) })
    await flush()
    expect(latest.state.currentId).toBe(8)
  })

  it('#18: a refused press takes back its marks and returns to the pressed card', async () => {
    await render()
    const answer = deferred()
    let running: Promise<unknown> = Promise.resolve()
    act(() => { running = latest.mutate(() => answer.promise, { phraseId: 41, closes: 'card' }) })
    expect(latest.state.currentId).toBe(42)
    await act(async () => {
      answer.reject(new Error('409: {"detail":"Already known"}'))
      await running.catch(() => {})
    })
    expect(latest.state.currentId).toBe(41)
    expect(latest.state.done.has(41)).toBe(false)
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
    vi.mocked(api.reviewText).mockResolvedValue(reviewUpdate({ text: CHUNK, header: header({ busy: true }) }))
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

  it('a gone set shows nothing to review', async () => {
    vi.mocked(api.openReview).mockRejectedValue(new Error('404: gone'))
    await render()
    expect(latest.gone).toBe(true)
  })

  describe('text', () => {
    const marks = () => [...host.querySelectorAll<HTMLElement>('[data-mark-id]')]
      .map(m => `${m.dataset.markId}:${m.className.match(/mark(Current|Rated|Pending)/)?.[1]}`)

    it('opens, then reads the contents, then exactly one chunk: the one at the current card', async () => {
      await render()
      expect(vi.mocked(api.reviewContents).mock.calls).toEqual([[{ review_id: REVIEW_ID, since: 1, current: 41 }]])
      expect(vi.mocked(api.reviewText).mock.calls).toEqual([[{ review_id: REVIEW_ID, since: 1, current: 41 }, 1, { block: TEXT_BLOCK }]])
      expect(latest.hasSourceText).toBe(true)
      expect(marks()).toEqual(['41:Current', '90:Pending'])
    })

    it('without a current card opens the first chunk of the first document', async () => {
      vi.mocked(api.openReview).mockResolvedValue(reviewUpdate({ layout: layout([], { replace: true }) }))
      await render()
      expect(vi.mocked(api.reviewText).mock.calls.map(([, sourceId, block]) => [sourceId, block])).toEqual([[1, { block: 0 }]])
    })

    it('a reopen after 410 sends every loaded chunk and takes their returned highlights', async () => {
      await render()
      vi.mocked(api.openReview).mockResolvedValue(windowAround(41, {
        review_id: 'r2', revision: 3,
        highlights: [{ source_id: 1, first_block: TEXT_BLOCK, highlights: [highlight(90, TEXT_BLOCK, 5, 8, true)] }],
      }))
      vi.mocked(api.reviewContents).mockResolvedValue(contents([1, 'Pilot', 50_000]))
      const press = vi.fn(async (ctx: ReviewContext) => {
        if (ctx.review_id === REVIEW_ID) throw new ReviewExpiredError('{"detail":"review_expired"}')
        return reviewUpdate({ review_id: 'r2', revision: 3 })
      })

      await act(async () => { await latest.mutate(press) })
      await flush()

      expect(vi.mocked(api.openReview).mock.lastCall?.[0].text_chunks).toEqual([{ source_id: 1, first_block: TEXT_BLOCK }])
      expect(marks()).toEqual(['90:Rated'])
      expect(api.reviewText).toHaveBeenCalledTimes(1)
      expect(latest.text.reviewId).toBe('r2')
    })

    it('reads the contents again when an answer brings another contents version', async () => {
      await render()
      vi.mocked(api.reviewContents).mockResolvedValue({ ...contents([1, 'Pilot'], [2, 'Episode 2']), version: 1 })
      await act(async () => { await latest.mutate(async () => reviewUpdate({ revision: 2, contents_version: 1 })) })
      await flush()
      expect(api.reviewContents).toHaveBeenCalledTimes(2)
      expect(latest.text.contents?.documents.map(d => d.title)).toEqual(['Pilot', 'Episode 2'])
      expect(host.textContent).toContain('Episode 2')

      await act(async () => { await latest.mutate(async () => reviewUpdate({ revision: 3, contents_version: 1 })) })
      await flush()
      expect(api.reviewContents).toHaveBeenCalledTimes(2)
    })

    it('the highlights a boundary edit brings change the marks; no chunk is read again', async () => {
      await render()
      await act(async () => {
        await latest.mutate(async () => reviewUpdate({
          revision: 2, highlights: [{ source_id: 1, first_block: TEXT_BLOCK, highlights: [highlight(41, TEXT_BLOCK, 0, 8)] }],
        }))
      })
      expect(marks()).toEqual(['41:Current'])
      expect(host.querySelector('[data-mark-id="41"]')?.textContent).toBe('near far')
      expect(api.reviewText).toHaveBeenCalledTimes(1)
    })

    it('takes the highlights of an answer it drops as stale', async () => {
      await render()
      await act(async () => { await latest.mutate(async () => reviewUpdate({ revision: 5 })) })
      await act(async () => {
        await latest.mutate(async () => reviewUpdate({
          revision: 4, highlights: [{ source_id: 1, first_block: TEXT_BLOCK, highlights: [highlight(90, TEXT_BLOCK, 5, 8)] }],
        }))
      })
      expect(latest.state.revision).toBe(5)
      expect(marks()).toEqual(['90:Pending'])
    })

    it('asks once for a chunk by character offset while the same one is in flight', async () => {
      await render()
      await act(async () => { await Promise.all([latest.loadText(1, { at: 12_345 }), latest.loadText(1, { at: 12_345 })]) })
      expect(vi.mocked(api.reviewText).mock.calls.slice(1).map(([, sourceId, place]) => [sourceId, place])).toEqual([[1, { at: 12_345 }]])
    })

    it('has no whole-documents read', () => {
      expect('getReviewDocuments' in api).toBe(false)
    })
  })
})
