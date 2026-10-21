import { describe, expect, it } from 'vitest'
import { sectionToggleLabel } from './sections'

describe('sectionToggleLabel', () => {
  it('names the reviewed group', () => {
    expect(sectionToggleLabel('reviewed', 1, false)).toBe('Show 1 reviewed phrase')
    expect(sectionToggleLabel('reviewed', 3, true)).toBe('Hide reviewed phrases')
  })
})
