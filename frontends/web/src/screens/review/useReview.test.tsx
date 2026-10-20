import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { CandidateSection, GenerationOverview, ReviewDetail, SetScope, StoredCandidate } from '@/api/types'
import { autoPlayAudioPref, sortOrderPref } from '@/lib/preferences'
import { buttons, state } from './reviewFixtures'
import { useReview, type Review } from './useReview'

const SCOPE: SetScope = 'source-7'
const POLL_MS = 3000

const card = (id: number, section: CandidateSection, isDone = section === 'reviewed') =>
  ({ phrase_id: id, word_id: id, section, is_done: isDone, state: state() }) as StoredCandidate
const detail = (candidates: StoredCandidate[]) =>
  ({ scope: SCOPE, candidates, busy: false, progress: { decided: 0, total: 0 } }) as unknown as ReviewDetail

// При загрузке: 1 и 2 в Ready, 3 уже разобрана.
const LOADED = [card(1, 'ready'), card(2, 'ready'), card(3, 'reviewed')]
// Как backend раскладывает после Learn на 1: она в Reviewed.
const AFTER_PRESS = [card(2, 'ready'), card(1, 'reviewed'), card(3, 'reviewed')]

function Probe({ onRender }: { onRender: (review: Review) => void }) {
  onRender(useReview(SCOPE))
  return null
}

const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })
const layout = (review: Review) => review.candidates.map(c => `${c.phrase_id}:${c.section}`)

describe('useReview layout', () => {
  let root: Root
  let latest: Review
  let backend: StoredCandidate[]

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    sortOrderPref.write('relevance')
    autoPlayAudioPref.write(false)
    backend = LOADED
    vi.spyOn(api, 'getReportReasons').mockResolvedValue([])
    vi.spyOn(api, 'getReview').mockImplementation(async () => detail(backend))
    vi.spyOn(api, 'getReviewDocuments').mockResolvedValue([])
    vi.spyOn(api, 'getReviewGeneration').mockResolvedValue({ in_progress: true } as GenerationOverview)
    vi.spyOn(api, 'decidePhrase').mockImplementation(async id => {
      backend = AFTER_PRESS
      return AFTER_PRESS.find(c => c.phrase_id === id)!
    })
    root = createRoot(document.createElement('div'))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('keeps a pressed card in place through polls and regroups on a sort change', async () => {
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()
    expect(layout(latest)).toEqual(['1:ready', '2:ready', '3:reviewed'])
    expect(latest.currentId).toBe(1)

    await act(async () => { await latest.press(1, buttons()[0]) })
    expect(layout(latest)).toEqual(['1:ready', '2:ready', '3:reviewed'])
    expect(latest.candidates[0].is_done).toBe(true)
    expect(latest.currentId).toBe(2)

    const reads = vi.mocked(api.getReview).mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS) })
    await flush()
    expect(vi.mocked(api.getReview).mock.calls.length).toBeGreaterThan(reads)
    expect(layout(latest)).toEqual(['1:ready', '2:ready', '3:reviewed'])

    await act(async () => latest.setSortOrder('key_words'))
    await flush()
    expect(layout(latest)).toEqual(['2:ready', '1:reviewed', '3:reviewed'])
  })

  it('loads the review, documents and generation of its scope', async () => {
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()
    expect(api.getReview).toHaveBeenCalledWith(SCOPE, 'relevance')
    expect(api.getReviewDocuments).toHaveBeenCalledWith(SCOPE)
    expect(api.getReviewGeneration).toHaveBeenCalledWith(SCOPE)
  })

  it('polls while a source of the set is busy', async () => {
    vi.mocked(api.getReviewGeneration).mockResolvedValue({ in_progress: false, kinds: [] })
    vi.mocked(api.getReview).mockImplementation(async () => ({ ...detail(backend), busy: true }))
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()
    const reads = vi.mocked(api.getReview).mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS) })
    await flush()
    expect(vi.mocked(api.getReview).mock.calls.length).toBeGreaterThan(reads)
  })

  it('toasts the reason of a refused press and of a refused cloze save, not the raw response', async () => {
    const refused = new Error('409: {"detail":"Already known"}')
    vi.mocked(api.decidePhrase).mockRejectedValue(refused)
    vi.spyOn(api, 'saveCloze').mockRejectedValue(new Error('409: {"detail":"Phrase 1 is already in Anki"}'))
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()

    await act(async () => { await latest.press(1, buttons()[0]) })
    expect(latest.toast).toBe('Already known')

    await act(async () => {
      await latest.saveCloze(1, { phrase: 'p', hidden_word_indices: [0], hint_kind: 'none', custom_hint: null })
    })
    expect(latest.toast).toBe('Phrase 1 is already in Anki')
  })

  it('opens the cloze editor on a Cloze that edits, without a decision or a focus move', async () => {
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()

    await act(async () => { await latest.press(1, buttons({ cloze: { command: 'edit_cloze' } })[1]) })

    expect(latest.clozeEditingId).toBe(1)
    expect(latest.currentId).toBe(1)
    expect(api.decidePhrase).not.toHaveBeenCalled()
  })

  it('sends a Cloze that decides, as on a cloze card, and closes the editor', async () => {
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()
    await act(async () => { await latest.press(1, buttons({ cloze: { command: 'edit_cloze' } })[1]) })

    await act(async () => { await latest.press(1, buttons()[1]) })

    expect(api.decidePhrase).toHaveBeenCalledWith(1, 'cloze')
    expect(latest.clozeEditingId).toBeNull()
  })

  it('does nothing on a refused button', async () => {
    await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
    await flush()

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
    backend = LOADED.map(withAudio)
    vi.mocked(api.decidePhrase).mockImplementation(async id => {
      backend = AFTER_PRESS.map(withAudio)
      return backend.find(c => c.phrase_id === id)!
    })
    autoPlayAudioPref.write(true)
    try {
      await act(async () => root.render(<Probe onRender={review => { latest = review }} />))
      await flush()
      await act(async () => { await latest.press(1, buttons()[0]) })
      await act(async () => latest.setCurrentId(3))

      expect(played).toEqual(['/media/7/1.m4a', '/media/7/2.m4a', '/media/7/3.m4a'])
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
