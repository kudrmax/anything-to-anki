import { describe, expect, it } from 'vitest'
import { highlightParts, meaningParts, mediaUrl, parseExamples, primaryUsageGroup } from './meaning'

describe('highlightParts', () => {
  it('marks the first occurrence of the surface form', () => {
    expect(highlightParts('She figured out the riddle', 'figure out', 'figured out')).toEqual([
      { text: 'She ', bold: false, target: false },
      { text: 'figured out', bold: false, target: true },
      { text: ' the riddle', bold: false, target: false },
    ])
  })
  it('falls back to the lemma with any ending', () => {
    expect(highlightParts('He procrastinates daily', 'procrastinate', null)[1]).toEqual({ text: 'procrastinates', bold: false, target: true })
  })
  it('returns the whole fragment when nothing matches', () => {
    expect(highlightParts('Nothing here', 'squander', null)).toEqual([{ text: 'Nothing here', bold: false, target: false }])
  })
  it('strips markdown markers', () => {
    expect(highlightParts('a **reckless** move', 'reckless', null).map(p => p.text).join('')).toBe('a reckless move')
  })
})

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
  it('parses example lines without bold markers and blanks', () => {
    expect(parseExamples('He **ran** off.\n\n She left. ')).toEqual(['He ran off.', 'She left.'])
    expect(parseExamples(null)).toEqual([])
  })
  it('hides the neutral usage group', () => {
    expect(primaryUsageGroup({ neutral: 1 })).toBeNull()
    expect(primaryUsageGroup({ informal: 0.7, neutral: 0.3 })).toBe('informal')
    expect(primaryUsageGroup(null)).toBeNull()
  })
})
