import { describe, expect, it } from 'vitest'
import { meaningAction, meaningParts, mediaUrl, primaryUsageGroup } from './meaning'

describe('meaningParts', () => {
  it('marks every occurrence and keeps bold runs', () => {
    expect(meaningParts('To **waste** it: squander, squandered', 'squander', null)).toEqual([
      { text: 'To ', bold: false, target: false },
      { text: 'waste', bold: true, target: false },
      { text: ' it: ', bold: false, target: false },
      { text: 'squander', bold: false, target: true },
      { text: ', ', bold: false, target: false },
      { text: 'squandered', bold: false, target: true },
    ])
  })
})

describe('helpers', () => {
  it('builds a media url from the file name only', () => {
    expect(mediaUrl(3, '/data/media/3/shot_12.jpg')).toBe('/media/3/shot_12.jpg')
    expect(mediaUrl(3, null)).toBeNull()
  })
  it('hides the neutral usage group', () => {
    expect(primaryUsageGroup({ neutral: 1 })).toBeNull()
    expect(primaryUsageGroup({ informal: 0.7, neutral: 0.3 })).toBe('informal')
    expect(primaryUsageGroup(null)).toBeNull()
  })
})

describe('meaningAction', () => {
  const meaning = (status: 'queued' | 'running' | 'done' | 'failed' | 'idle', text: string | null = null) =>
    ({ meaning: text, translation: null, synonyms: null, examples: null, ipa: null, status, error: null, generated_at: null })

  it('offers generation when there is no meaning yet', () => {
    expect(meaningAction(null)).toBe('generate')
    expect(meaningAction(meaning('idle'))).toBe('generate')
    expect(meaningAction(meaning('queued'))).toBe('generate')
  })
  it('offers a retry after a failed generation', () => {
    expect(meaningAction(meaning('failed'))).toBe('retry')
  })
  it('offers nothing while generating or once the text exists', () => {
    expect(meaningAction(meaning('running'))).toBeNull()
    expect(meaningAction(meaning('done', 'A definition'))).toBeNull()
  })
})
