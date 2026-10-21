import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { ApiError } from '@/api/errors'
import type { GenerateMeaningResult, GenerationOverview, SetScope, StoredCandidate } from '@/api/types'
import { autoPlayAudioPref, sortOrderPref } from '@/lib/preferences'
import { buttons, cardRow, layout, reviewCard, reviewUpdate, state } from './reviewFixtures'
import { useReview, type Review } from './useReview'

const SCOPE: SetScope = 'source-7'

const card = (id: number, isDone = false) => ({ ...reviewCard({ phrase_id: id, word_id: id, is_done: isDone }), state: state() }) as StoredCandidate
const opened = (cards: StoredCandidate[]) => reviewUpdate({
  layout: layout(cards.map((c, i) => cardRow(i, c.phrase_id)), { replace: true }), cards, focus_id: cards[0].phrase_id,
})

function Probe({ onRender }: { onRender: (review: Review) => void }) {
  onRender(useReview(SCOPE))
  return null
}

const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })

describe('useReview', () => {
  let root: Root
  let latest: Review
  let loaded: StoredCandidate[]

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    sortOrderPref.write('relevance')
    autoPlayAudioPref.write(false)
    loaded = [card(1), card(2), card(3, true)]
    vi.spyOn(api, 'getReportReasons').mockResolvedValue([])
    vi.spyOn(api, 'openReview').mockImplementation(async () => opened(loaded))
    vi.spyOn(api, 'getReviewDocuments').mockResolvedValue([])
    vi.spyOn(api, 'getReviewGeneration').mockResolvedValue({ in_progress: false } as GenerationOverview)
    // Как отвечает backend на Learn: карточка разобрана, фокус — на следующую.
    vi.spyOn(api, 'decidePhrase').mockImplementation(async (_ctx, id) =>
      reviewUpdate({ revision: 2, cards: [card(id, true)], done: { [id]: true }, focus_id: id + 1 }))
    root = createRoot(document.createElement('div'))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.restoreAllMocks()
  })

  const render = async () => {
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()
  }

  it('a press keeps the rows where they are, takes the fresh card and moves to the focus the backend gives', async () => {
    await render()
    expect(latest.currentId).toBe(1)

    await act(async () => { await latest.press(1, buttons()[0]) })

    expect(api.decidePhrase).toHaveBeenCalledWith({ review_id: 'r1', since: 1, current: 1 }, 1, 'learn')
    expect([...latest.state.rows.values()].map(r => r.phrase_id)).toEqual([1, 2, 3])
    expect(latest.state.cards.get(1)?.is_done).toBe(true)
    expect(latest.currentId).toBe(2)
  })

  it('opens the review of its scope again, on the current card, when the sort changes', async () => {
    await render()
    await act(async () => { await latest.goTo(2) })
    await act(async () => latest.setSortOrder('key_words'))
    await flush()
    expect(vi.mocked(api.openReview).mock.lastCall).toEqual([{ scope: SCOPE, sort: 'key_words', requested_id: 2, open_sections: [] }])
    expect(api.getReviewDocuments).toHaveBeenCalledWith(SCOPE)
    expect(api.getReviewGeneration).toHaveBeenCalledWith(SCOPE)
  })

  it('shows the AI-unavailable banner when making a meaning fails with 503, and toasts other failures', async () => {
    vi.spyOn(api, 'generateMeaning').mockRejectedValue(new ApiError(503, '{"detail":"Blocked country"}'))
    await render()
    await act(async () => { await latest.generate(1) })
    expect(latest.vpnBlocked).toBe(true)

    act(() => latest.dismissVpn())
    vi.mocked(api.generateMeaning).mockRejectedValue(new ApiError(502, '{"detail":"Model is down"}'))
    await act(async () => { await latest.generate(1) })
    expect(latest.vpnBlocked).toBe(false)
    expect(latest.toast).toContain('Model is down')
  })

  it('applies the update a meaning brings and toasts the tokens', async () => {
    vi.spyOn(api, 'generateMeaning').mockResolvedValue({
      tokens_used: 12, update: reviewUpdate({ revision: 2, cards: [{ ...card(1), lemma: 'glare' }] }),
    } as GenerateMeaningResult)
    await render()
    await act(async () => { await latest.generate(1) })
    expect(latest.state.cards.get(1)?.lemma).toBe('glare')
    expect(latest.toast).toBe('Tokens used: 12')
  })

  it('toasts the reason of a refused press and of a refused cloze save, not the raw response', async () => {
    const refused = new Error('409: {"detail":"Already known"}')
    vi.mocked(api.decidePhrase).mockRejectedValue(refused)
    vi.spyOn(api, 'saveCloze').mockRejectedValue(new Error('409: {"detail":"Phrase 1 is already in Anki"}'))
    await render()

    await act(async () => { await latest.press(1, buttons()[0]) })
    expect(latest.toast).toBe('Already known')

    await act(async () => {
      await latest.saveCloze(1, { phrase: 'p', hidden_word_indices: [0], hint_kind: 'none', custom_hint: null })
    })
    expect(latest.toast).toBe('Phrase 1 is already in Anki')
  })

  it('opens the cloze editor on a Cloze that edits, without a decision or a focus move', async () => {
    await render()

    await act(async () => { await latest.press(1, buttons({ cloze: { command: 'edit_cloze' } })[1]) })

    expect(latest.clozeEditingId).toBe(1)
    expect(latest.currentId).toBe(1)
    expect(api.decidePhrase).not.toHaveBeenCalled()
  })

  it('sends a Cloze that decides, as on a cloze card, and closes the editor', async () => {
    await render()
    await act(async () => { await latest.press(1, buttons({ cloze: { command: 'edit_cloze' } })[1]) })

    await act(async () => { await latest.press(1, buttons()[1]) })

    expect(api.decidePhrase).toHaveBeenCalledWith(expect.anything(), 1, 'cloze')
    expect(latest.clozeEditingId).toBeNull()
  })

  it('does nothing on a refused button', async () => {
    await render()

    await act(async () => { await latest.press(1, buttons({ learn: { command: null, refused: 'not_decision_card' } })[0]) })

    expect(api.decidePhrase).not.toHaveBeenCalled()
    expect(latest.currentId).toBe(1)
  })

  it('plays the audio of every card it shows: on opening, after a decision and on moving', async () => {
    const played: string[] = []
    vi.stubGlobal('Audio', class {
      constructor(url: string) { played.push(url) }
      addEventListener() {}
      pause() {}
      play() { return Promise.resolve() }
    })
    const withAudio = (c: StoredCandidate) => ({ ...c, source: { id: 7 }, audio_path: `m/${c.phrase_id}.m4a` }) as StoredCandidate
    loaded = loaded.map(withAudio)
    vi.mocked(api.decidePhrase).mockImplementation(async (_ctx, id) =>
      reviewUpdate({ revision: 2, cards: [withAudio(card(id, true))], focus_id: id + 1 }))
    autoPlayAudioPref.write(true)
    try {
      await render()
      await act(async () => { await latest.press(1, buttons()[0]) })
      await act(async () => { await latest.goTo(3) })

      expect(played).toEqual(['/media/7/1.m4a', '/media/7/2.m4a', '/media/7/3.m4a'])
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
