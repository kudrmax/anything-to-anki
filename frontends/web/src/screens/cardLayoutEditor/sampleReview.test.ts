import { describe, expect, it } from 'vitest'
import type { OpenReviewRequest } from '@/api/types'
import { DEFAULT_SAMPLE_PARTS, toggleSamplePart } from './sampleParts'
import { SAMPLE_SCOPE, sampleReviewApi } from './sampleReview'

const CONTEXT = { review_id: 'layout-sample', since: 0, current: null }
const OPEN: OpenReviewRequest = { scope: String(SAMPLE_SCOPE), sort: 'relevance', requested_id: null, open_sections: [], text_chunks: [] }

const sampleCard = async (parts = DEFAULT_SAMPLE_PARTS) => {
  const opened = await sampleReviewApi(parts).openReview(OPEN)
  expect(opened.cards).toHaveLength(1)
  expect(opened.focus_id).toBe(opened.cards[0].phrase_id)
  return opened.cards[0]
}

describe('sample review of the layout editor', () => {
  it('shows one card with everything but the picture choice by default', async () => {
    const card = await sampleCard()
    expect([card.meaning?.meaning?.split('\n').length, card.meaning_action]).toEqual([3, null])
    expect([card.meaning_image_path !== null, card.media !== null, card.tts !== null, card.pronunciation !== null]).toEqual([true, true, true, true])
  })

  it('leaves out what is switched off: no meaning offers Generate meaning', async () => {
    const card = await sampleCard(toggleSamplePart(toggleSamplePart(DEFAULT_SAMPLE_PARTS, 'meaning'), 'tts'))
    expect([card.meaning, card.meaning_action, card.tts]).toEqual([null, 'generate', null])
  })

  it('never has a chosen picture and a picture choice at once', async () => {
    const choosing = toggleSamplePart(DEFAULT_SAMPLE_PARTS, 'picture_choice')
    expect([choosing.has('picture'), choosing.has('picture_choice')]).toEqual([false, true])
    expect((await sampleCard(choosing)).meaning_image_path).toBeNull()
    expect((await sampleReviewApi(choosing).suggestTargetImages(1)).options.length).toBeGreaterThan(0)
    const chosen = toggleSamplePart(choosing, 'picture')
    expect([chosen.has('picture'), chosen.has('picture_choice')]).toEqual([true, false])
  })

  it('highlights the card target in the source text', async () => {
    const { text } = await sampleReviewApi(DEFAULT_SAMPLE_PARTS).reviewText(CONTEXT, 0, { block: 0 })
    const line = text!.blocks[0].lines[0].text
    expect(text!.highlights.map(h => line.slice(h.position.start_char, h.position.end_char))).toEqual(['glared'])
  })

  it('changes nothing: every change is refused', async () => {
    const api = sampleReviewApi(DEFAULT_SAMPLE_PARTS)
    await expect(api.decidePhrase(CONTEXT, 1, 'learn')).rejects.toThrow()
    await expect(api.generateMeaning(CONTEXT, 1)).rejects.toThrow()
  })
})
