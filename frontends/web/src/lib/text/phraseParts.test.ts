import { describe, expect, it } from 'vitest'
import { phraseParts, targetText, touchesMarks, wordGroups } from './phraseParts'

const PHRASE = { text: 'She gave it up.', words: [[0, 3], [4, 8], [9, 11], [12, 14]] as [number, number][], target: [1, 3] }

describe('phraseParts', () => {
  it('cuts the text by words and keeps what lies between them', () => {
    expect(phraseParts(PHRASE).map(p => p.text)).toEqual(['She', ' ', 'gave', ' ', 'it', ' ', 'up', '.'])
  })

  it('marks the target and the hidden words by number', () => {
    const parts = phraseParts(PHRASE, new Set([2]))
    expect(parts.filter(p => p.target).map(p => p.text)).toEqual(['gave', 'up'])
    expect(parts.filter(p => p.hidden).map(p => p.text)).toEqual(['it'])
  })
})

describe('targetText', () => {
  it('joins the target words as written', () => {
    expect(targetText(PHRASE)).toBe('gave up')
  })
})

describe('wordGroups', () => {
  it('keeps punctuation with the word it touches and drops the spaces', () => {
    const groups = wordGroups(phraseParts(PHRASE)).map(group => group.map(part => part.text).join(''))

    expect(groups).toEqual(['She', 'gave', 'it', 'up.'])
  })

  it('keeps a quote and a comma around their word', () => {
    const phrase = { text: '"Hi," she said', words: [[1, 3], [6, 9], [10, 14]], target: [0] } as typeof PHRASE

    expect(wordGroups(phraseParts(phrase)).map(group => group.map(part => part.text).join(''))).toEqual(['"Hi,"', 'she', 'said'])
  })
})

describe('touchesMarks', () => {
  it('tells which side of a word a mark stands on', () => {
    const phrase = { text: '"Hi," she said', words: [[1, 3], [6, 9], [10, 14]], target: [0] } as typeof PHRASE
    const [quoted, plain] = wordGroups(phraseParts(phrase))

    expect(touchesMarks(quoted, 1)).toEqual({ before: true, after: true })
    expect(touchesMarks(plain, 0)).toEqual({ before: false, after: false })
  })
})
