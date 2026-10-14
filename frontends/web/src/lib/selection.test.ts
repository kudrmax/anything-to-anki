import { describe, expect, it } from 'vitest'
import { clickSelect, EMPTY_SELECTION, pruned, selectAll } from './selection'

const ORDER = [5, 4, 3, 2, 1]
const ids = (s: { ids: ReadonlySet<number> }) => [...s.ids].sort()

describe('selection', () => {
  it('toggle adds and removes', () => {
    const one = clickSelect(EMPTY_SELECTION, ORDER, 4, { toggle: true, range: false })
    expect(ids(one)).toEqual([4])
    expect(ids(clickSelect(one, ORDER, 4, { toggle: true, range: false }))).toEqual([])
  })
  it('range goes from anchor to the clicked row', () => {
    const anchor = clickSelect(EMPTY_SELECTION, ORDER, 4, { toggle: true, range: false })
    expect(ids(clickSelect(anchor, ORDER, 2, { toggle: false, range: true }))).toEqual([2, 3, 4])
  })
  it('a plain click toggles while something is selected', () => {
    const one = clickSelect(EMPTY_SELECTION, ORDER, 4, { toggle: true, range: false })
    expect(ids(clickSelect(one, ORDER, 1, { toggle: false, range: false }))).toEqual([1, 4])
  })
  it('select all and prune', () => {
    expect(ids(selectAll(ORDER))).toEqual([1, 2, 3, 4, 5])
    expect(ids(pruned(selectAll(ORDER), [1, 2]))).toEqual([1, 2])
  })
})
