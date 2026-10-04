import { describe, expect, it } from 'vitest'
import { normalizePhrase, snapToWords } from './targetSpan'

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
