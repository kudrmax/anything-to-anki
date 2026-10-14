import { describe, expect, it } from 'vitest'
import { phraseParts, targetText } from './phraseParts'

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
