import { describe, expect, it } from 'vitest'
import { normalizePhrase, pickSpan, segments, snapToWords, targetText } from './targetSpan'

const TEXT = "Now it's time to stop relying on those subtitles."

const spanOf = (word: string) => {
  const start = TEXT.indexOf(word)
  return { start, end: start + word.length }
}

describe('snapToWords', () => {
  it('extends a partial selection to the whole word', () => {
    const { start } = spanOf('relying')
    expect(snapToWords(TEXT, start + 2, start + 4)).toEqual(spanOf('relying'))
  })

  it('covers every word a selection touches', () => {
    const { start } = spanOf('relying on')
    expect(snapToWords(TEXT, start + 3, start + 9)).toEqual(spanOf('relying on'))
  })

  it('drops surrounding spaces and punctuation', () => {
    const { start, end } = spanOf('subtitles')
    expect(snapToWords(TEXT, start - 1, end + 1)).toEqual(spanOf('subtitles'))
  })

  it('keeps apostrophes inside a word', () => {
    const { start } = spanOf("it's")
    expect(snapToWords(TEXT, start, start + 1)).toEqual(spanOf("it's"))
  })

  it('accepts a backwards selection', () => {
    const { start, end } = spanOf('stop')
    expect(snapToWords(TEXT, end, start)).toEqual(spanOf('stop'))
  })

  it('ignores a selection without letters', () => {
    const { end } = spanOf('subtitles')
    expect(snapToWords(TEXT, end, end + 1)).toBeNull()
  })
})

describe('normalizePhrase', () => {
  it('collapses line breaks and repeated spaces', () => {
    expect(normalizePhrase('  can follow\n  most  things \n')).toBe('can follow most things')
  })
})

const PHRASAL = 'Never give it up now'
const GIVE = { start: 6, end: 10 }
const UP = { start: 14, end: 16 }

describe('pickSpan', () => {
  it('replaces the target without adding', () => {
    expect(pickSpan([GIVE], UP, false)).toEqual([UP])
  })

  it('adds a separated part in phrase order', () => {
    expect(pickSpan([UP], GIVE, true)).toEqual([GIVE, UP])
  })

  it('removes a part picked again', () => {
    expect(pickSpan([GIVE, UP], { start: 7, end: 9 }, true)).toEqual([UP])
  })
})

describe('targetText', () => {
  it('joins the parts with spaces', () => {
    expect(targetText(PHRASAL, [GIVE, UP])).toBe('give up')
  })
})

describe('segments', () => {
  it('marks picked parts and keeps the rest of the phrase', () => {
    expect(segments(PHRASAL, [GIVE, UP])).toEqual([
      { text: 'Never ', picked: false },
      { text: 'give', picked: true },
      { text: ' it ', picked: false },
      { text: 'up', picked: true },
      { text: ' now', picked: false },
    ])
  })
})
