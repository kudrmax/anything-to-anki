import { describe, expect, it } from 'vitest'
import { SAMPLE_REVIEW_API, SAMPLE_SCOPE } from './sampleReview'

const CONTEXT = { review_id: 'layout-sample', since: 0, current: null }

describe('sample review of the layout editor', () => {
  it('opens on the first card with every card of the sample, each in its own state', async () => {
    const opened = await SAMPLE_REVIEW_API.openReview({ scope: String(SAMPLE_SCOPE), sort: 'relevance', requested_id: null, open_sections: [], text_chunks: [] })
    const [full, noPicture, withNotes, noMeaning] = opened.cards
    expect(opened.focus_id).toBe(full.phrase_id)
    expect(opened.layout?.total_cards).toBe(opened.cards.length)
    expect([full.meaning_image_path !== null, full.media !== null, full.tts !== null]).toEqual([true, true, true])
    expect(noPicture.meaning_image_path).toBeNull()
    expect(withNotes.meaning?.meaning?.split('\n')).toHaveLength(3)
    expect([noMeaning.meaning, noMeaning.meaning_action]).toEqual([null, 'generate'])
  })

  it('highlights each card target in the source text', async () => {
    const { text } = await SAMPLE_REVIEW_API.reviewText(CONTEXT, 0, { block: 0 })
    const line = text!.blocks[0].lines[0].text
    const marked = text!.highlights.map(h => line.slice(h.position.start_char, h.position.end_char))
    expect(marked).toEqual(['glared', 'placate', 'give', 'concession'])
  })

  it('changes nothing: every change is refused', async () => {
    await expect(SAMPLE_REVIEW_API.decidePhrase(CONTEXT, 1, 'learn')).rejects.toThrow()
    await expect(SAMPLE_REVIEW_API.generateMeaning(CONTEXT, 4)).rejects.toThrow()
  })
})
