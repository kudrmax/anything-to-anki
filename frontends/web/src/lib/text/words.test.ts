import { describe, expect, it } from 'vitest'
import { phraseWords, pickedIndices, pickedWords, wordsIn } from './words'

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

describe('wordsIn', () => {
  it('numbers the words a selection touches, the repeated one where it was picked', () => {
    const text = 'She runs fast, she runs more.'
    expect(wordsIn(text, [{ start: 19, end: 23 }])).toEqual([4])
  })

  it('counts words without the quotes around them', () => {
    expect(wordsIn('“Hello,” she said', [{ start: 9, end: 17 }])).toEqual([1, 2])
  })
})

describe('pickedIndices', () => {
  it('puts the picked numbers in text order', () => {
    expect(pickedIndices(new Set([3, 1]))).toEqual([1, 3])
  })
})
