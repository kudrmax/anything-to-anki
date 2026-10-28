import { describe, expect, it } from 'vitest'
import { meaningParts, mediaUrl } from './meaning'

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
})
