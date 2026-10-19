import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { CandidateSection, GenerationOverview, SourceDetail, StoredCandidate } from '@/api/types'
import { autoPlayAudioPref, sortOrderPref } from '@/lib/preferences'
import { useReview, type Review } from './useReview'

const SOURCE_ID = 7
const POLL_MS = 3000

const card = (id: number, section: CandidateSection, isDone = section === 'reviewed') =>
  ({ phrase_id: id, word_id: id, section, is_done: isDone, status: isDone ? 'learn' : 'pending' }) as StoredCandidate
const detail = (candidates: StoredCandidate[]) =>
  ({ id: SOURCE_ID, candidates, has_source_text: false, busy_with: null, progress: { decided: 0, total: 0 } }) as unknown as SourceDetail

// При загрузке: 1 и 2 в Ready, 3 уже разобрана.
const LOADED = [card(1, 'ready'), card(2, 'ready'), card(3, 'reviewed')]
// Как backend раскладывает после Learn на 1: она в Reviewed.
const AFTER_PRESS = [card(2, 'ready'), card(1, 'reviewed'), card(3, 'reviewed')]

function Probe({ onRender }: { onRender: (review: Review) => void }) {
  onRender(useReview(SOURCE_ID))
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
    vi.spyOn(api, 'getSource').mockImplementation(async () => detail(backend))
    vi.spyOn(api, 'getGenerationStatus').mockResolvedValue({ in_progress: true } as GenerationOverview)
    vi.spyOn(api, 'decidePhrase').mockImplementation(async id => { backend = AFTER_PRESS; return { id, status: 'learn' } })
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

    await act(async () => { await latest.mark(1, 'learn') })
    expect(layout(latest)).toEqual(['1:ready', '2:ready', '3:reviewed'])
    expect(latest.candidates[0].is_done).toBe(true)
    expect(latest.currentId).toBe(2)

    const reads = vi.mocked(api.getSource).mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS) })
    await flush()
    expect(vi.mocked(api.getSource).mock.calls.length).toBeGreaterThan(reads)
    expect(layout(latest)).toEqual(['1:ready', '2:ready', '3:reviewed'])

    await act(async () => latest.setSortOrder('key_words'))
    await flush()
    expect(layout(latest)).toEqual(['2:ready', '1:reviewed', '3:reviewed'])
  })
})
