import { describe, expect, it } from 'vitest'
import { DEFAULT_SAMPLE_PARTS, sampleContext, toggleSamplePart } from './sampleCard'

describe('sample card parts', () => {
  it('turns a part off and on again', () => {
    const off = toggleSamplePart(DEFAULT_SAMPLE_PARTS, 'tts')
    expect(off.has('tts')).toBe(false)
    expect(toggleSamplePart(off, 'tts').has('tts')).toBe(true)
  })

  it('never has a chosen picture and a picture choice at once', () => {
    const choosing = toggleSamplePart(DEFAULT_SAMPLE_PARTS, 'picture_choice')
    expect([choosing.has('picture'), choosing.has('picture_choice')]).toEqual([false, true])
    const chosen = toggleSamplePart(choosing, 'picture')
    expect([chosen.has('picture'), chosen.has('picture_choice')]).toEqual([true, false])
  })

  it('offers Generate meaning only when the sample has no meaning', () => {
    expect(sampleContext(DEFAULT_SAMPLE_PARTS).candidate.meaning_action).toBeNull()
    const bare = sampleContext(toggleSamplePart(DEFAULT_SAMPLE_PARTS, 'meaning')).candidate
    expect([bare.meaning, bare.meaning_action]).toEqual([null, 'generate'])
  })
})
