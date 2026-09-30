import { describe, expect, it } from 'vitest'
import { findMark } from './findMark'

const container = (html: string) => {
  const div = document.createElement('div')
  div.innerHTML = html
  return div
}

describe('findMark', () => {
  it('finds the mark of the candidate itself', () => {
    const root = container('<mark data-mark-id="1">reckless</mark> <mark data-mark-id="2">behaviour</mark>')
    expect(findMark(root, 2, 'his reckless behaviour')?.textContent).toBe('behaviour')
  })
  it('falls back to another mark inside the same fragment when its own is covered', () => {
    const root = container('I was <mark data-mark-id="7">burst out</mark> laughing. <mark data-mark-id="9">fraught</mark>')
    expect(findMark(root, 8, 'the riddle and  burst out laughing')?.textContent).toBe('burst out')
  })
  it('returns null when nothing in the text belongs to the fragment', () => {
    const root = container('<mark data-mark-id="9">fraught</mark>')
    expect(findMark(root, 8, 'burst out laughing')).toBeNull()
  })
})
