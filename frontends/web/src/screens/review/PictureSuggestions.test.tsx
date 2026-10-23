import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { ImageOption, ImageSuggestions } from '@/api/types'
import { PictureSuggestions } from './PictureSuggestions'
import { cardRow, reviewCard } from './reviewFixtures'
import { initialState, type ReviewState } from './reviewState'
import type { Review } from './useReview'
import { SUGGESTION_POLL_MS, usePictureSuggestions, type PictureSuggestionsLoader } from './usePictureSuggestions'

const options = (word: number, count: number): ImageOption[] =>
  Array.from({ length: count }, (_, i) => ({ url: `https://pictures/${word}/${i}.jpg`, provider: 'bing' }))

const found = (word: number, count = 8): ImageSuggestions => ({ status: 'ready', query: `word${word}`, options: options(word, count) })

const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })

describe('picture suggestions', () => {
  let host: HTMLDivElement
  let root: Root
  let search: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
    search = vi.spyOn(api, 'suggestTargetImages').mockImplementation(async wordId => found(wordId))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.restoreAllMocks()
  })

  describe('on the card', () => {
    let review: Review

    beforeEach(() => {
      review = { applyImage: vi.fn(), busy: { image: new Set<number>() } } as unknown as Review
    })

    const render = (load: PictureSuggestionsLoader) =>
      act(() => root.render(<PictureSuggestions candidate={reviewCard({ phrase_id: 4, word_id: 9 })} review={review} load={load} />))
    const tiles = () => [...host.querySelectorAll('button')]

    it('offers the first five pictures and says they are only suggested', async () => {
      await render(async () => options(9, 5))
      await flush()
      expect(tiles()).toHaveLength(5)
      expect(host.textContent).toContain('Suggested pictures')
    })

    it('adds the clicked picture to the card', async () => {
      await render(async () => options(9, 5))
      await flush()
      act(() => tiles()[2].click())
      expect(review.applyImage).toHaveBeenCalledWith(4, 'https://pictures/9/2.jpg')
    })

    it('shows nothing when no picture was found', async () => {
      await render(async () => [])
      await flush()
      expect(host.innerHTML).toBe('')
    })
  })

  describe('loading', () => {
    let latest: PictureSuggestionsLoader | null

    function Probe({ state, enabled, onRender }: { state: ReviewState; enabled: boolean; onRender: (load: PictureSuggestionsLoader | null) => void }) {
      onRender(usePictureSuggestions(state, enabled))
      return null
    }
    const probe = (state: ReviewState, enabled = true) =>
      act(() => root.render(<Probe state={state} enabled={enabled} onRender={load => { latest = load }} />))

    const reviewState = (pictured: number[] = []): ReviewState => {
      const cards = [1, 2, 3, 4, 5, 6, 7, 8].map(id =>
        reviewCard({ phrase_id: id, word_id: id * 10, meaning_image_path: pictured.includes(id) ? 'pic.jpg' : null }))
      return {
        ...initialState,
        rows: new Map(cards.map((card, i) => [i, cardRow(i, card.phrase_id)])),
        cards: new Map(cards.map(card => [card.phrase_id, card])),
        currentId: 1,
      }
    }
    const searchedWords = () => search.mock.calls.map((call: unknown[]) => call[0])

    it('searches the five next cards ahead, except those that already have a picture', async () => {
      probe(reviewState([3]))
      await flush()
      expect(searchedWords()).toEqual([20, 40, 50, 60])
    })

    it('keeps found pictures: the next card does not search again', async () => {
      probe(reviewState())
      await flush()
      search.mockClear()
      expect(await latest!(20)).toEqual(options(20, 5))
      expect(search).not.toHaveBeenCalled()
    })

    it('searches again after a failed search', async () => {
      search.mockRejectedValueOnce(new Error('offline'))
      probe({ ...reviewState(), currentId: 99 })
      expect(await latest!(10)).toEqual([])
      expect(await latest!(10)).toEqual(options(10, 5))
      expect(search).toHaveBeenCalledTimes(2)
    })

    it('#24: while the server still searches, asks again later and offers the pictures once found', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout'] })
      try {
        let first = true
        search.mockImplementation(async (wordId: number) => {
          if (wordId !== 10 || !first) return found(wordId)
          first = false
          return { status: 'searching', query: 'word10', options: [] }
        })
        probe(reviewState())
        const offered = latest!(10)
        await vi.advanceTimersByTimeAsync(SUGGESTION_POLL_MS)
        expect(await offered).toEqual(options(10, 5))
        expect(search.mock.calls.filter((call: unknown[]) => call[0] === 10)).toHaveLength(2)
      } finally {
        vi.useRealTimers()
      }
    })

    it('#24: stops asking about a word the screen moved past; asks again when it comes back', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout'] })
      try {
        search.mockResolvedValue({ status: 'searching', query: 'word20', options: [] })
        probe(reviewState())
        const offered = latest!(20)
        await vi.advanceTimersByTimeAsync(SUGGESTION_POLL_MS)
        const asked = search.mock.calls.filter((call: unknown[]) => call[0] === 20).length
        probe({ ...reviewState(), currentId: 8 })
        await vi.advanceTimersByTimeAsync(SUGGESTION_POLL_MS * 5)
        expect(await offered).toEqual([])
        expect(search.mock.calls.filter((call: unknown[]) => call[0] === 20).length).toBe(asked)
      } finally {
        vi.useRealTimers()
      }
    })

    it('#24: a search the server could not do offers nothing and is asked again next time', async () => {
      search.mockResolvedValueOnce({ status: 'failed', query: 'word10', options: [] })
      probe({ ...reviewState(), currentId: 99 })
      expect(await latest!(10)).toEqual([])
      expect(await latest!(10)).toEqual(options(10, 5))
    })

    it('neither searches nor offers anything when switched off', async () => {
      probe(reviewState(), false)
      await flush()
      expect(latest).toBeNull()
      expect(search).not.toHaveBeenCalled()
    })
  })
})
