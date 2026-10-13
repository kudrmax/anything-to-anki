import { describe, expect, it } from 'vitest'
import { codePointOffset, lineSegments, spanInLine } from './documentSegments'

const at = (block: number, startLine: number, startChar: number, endLine: number, endChar: number) => ({
  block, start_line: startLine, start_char: startChar, end_line: endLine, end_char: endChar,
})

describe('spanInLine', () => {
  it('takes the part of a position that falls in the line', () => {
    const position = at(1, 0, 4, 2, 3)
    expect(spanInLine(position, 1, 0, 10)).toEqual([4, 10])
    expect(spanInLine(position, 1, 1, 7)).toEqual([0, 7])
    expect(spanInLine(position, 1, 2, 9)).toEqual([0, 3])
    expect(spanInLine(position, 1, 3, 9)).toBeNull()
    expect(spanInLine(position, 0, 0, 9)).toBeNull()
  })
})

describe('lineSegments', () => {
  it('cuts the line at targets and at the edges of the phrase in focus', () => {
    const segments = lineSegments('He gave up the chase', 0, 0, [{ candidateId: 7, position: at(0, 0, 3, 0, 10) }], at(0, 0, 0, 0, 14))
    expect(segments).toEqual([
      { start: 0, text: 'He ', markId: null, inFragment: true },
      { start: 3, text: 'gave up', markId: 7, inFragment: true },
      { start: 10, text: ' the', markId: null, inFragment: true },
      { start: 14, text: ' chase', markId: null, inFragment: false },
    ])
  })

  it('counts characters in code points, as the backend does', () => {
    const segments = lineSegments('😀 relentless', 0, 0, [{ candidateId: 1, position: at(0, 0, 2, 0, 12) }], null)
    expect(segments.map(s => [s.start, s.text, s.markId])).toEqual([[0, '😀 ', null], [2, 'relentless', 1]])
  })
})

describe('codePointOffset', () => {
  it('turns a UTF-16 offset into code points', () => {
    expect(codePointOffset('😀 hi', 3)).toBe(2)
    expect(codePointOffset('plain', 3)).toBe(3)
  })
})
