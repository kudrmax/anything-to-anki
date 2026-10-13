import { describe, expect, it } from 'vitest'
import { pickedSpans } from './words'

describe('pickedSpans', () => {
  it('places the picked words in the phrase', () => {
    expect(pickedSpans('The  ominous creature lurked', new Set([1, 3]))).toEqual([
      { start: 5, end: 12 },
      { start: 22, end: 28 },
    ])
  })
})
