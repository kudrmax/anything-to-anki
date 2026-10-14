import { describe, expect, it } from 'vitest'
import { phraseWords, pickedWords } from './words'

describe('phraseWords', () => {
  it('leaves punctuation out of words and keeps contractions and hyphens in', () => {
    expect(phraseWords('“Hello,” she said — don\'t stop; well-known.')).toEqual(
      ['Hello', 'she', 'said', 'don\'t', 'stop', 'well-known'],
    )
  })
})

describe('pickedWords', () => {
  it('joins the picked words in text order', () => {
    expect(pickedWords('She gave it up.', new Set([3, 1]))).toBe('gave up')
  })
})
