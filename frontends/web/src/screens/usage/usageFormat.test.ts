import { describe, expect, it } from 'vitest'
import { formatChange, formatTokens, labelledIndexes, niceCeiling } from './usageFormat'

describe('niceCeiling', () => {
  it('rounds up to 1, 2 or 5 times a power of ten', () => {
    expect(niceCeiling(0)).toBe(1)
    expect(niceCeiling(7)).toBe(10)
    expect(niceCeiling(1_000)).toBe(1_000)
    expect(niceCeiling(1_001)).toBe(2_000)
    expect(niceCeiling(4_200_000)).toBe(5_000_000)
  })
})

describe('labelledIndexes', () => {
  it('labels every column when they fit', () => {
    expect([...labelledIndexes(7, 8)]).toEqual([0, 1, 2, 3, 4, 5, 6])
  })

  it('always labels the first and the last column', () => {
    const indexes = [...labelledIndexes(30, 6)]
    expect(indexes[0]).toBe(0)
    expect(indexes[indexes.length - 1]).toBe(29)
    expect(indexes.length).toBeLessThanOrEqual(6)
  })

  it('keeps labels apart near the end', () => {
    const indexes = [...labelledIndexes(16, 6)]
    const gaps = indexes.slice(1).map((index, i) => index - indexes[i])
    expect(Math.min(...gaps)).toBeGreaterThanOrEqual(2)
  })
})

describe('formatChange', () => {
  it('shows the sign of the change', () => {
    expect(formatChange(18.5, '30d')).toBe('+18.5% vs previous 30 days')
    expect(formatChange(-5, '7d')).toBe('−5% vs previous 7 days')
  })
})

describe('formatTokens', () => {
  it('uses compact notation', () => {
    expect(formatTokens(4_820_000)).toBe('4.8M')
    expect(formatTokens(950)).toBe('950')
  })
})
