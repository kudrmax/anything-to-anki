import { describe, expect, it } from 'vitest'
import { parseScope } from './scope'

describe('parseScope', () => {
  it('reads all, unsorted and ids', () => {
    expect(parseScope(null)).toBe('all')
    expect(parseScope('unsorted')).toBe('unsorted')
    expect(parseScope('12')).toBe(12)
  })
  it('falls back to all on garbage', () => {
    expect(parseScope('-3')).toBe('all')
    expect(parseScope('abc')).toBe('all')
  })
})
