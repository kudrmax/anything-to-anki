import { describe, expect, it } from 'vitest'
import { backIn, backTo } from './backLink'

describe('backIn', () => {
  it('returns the path the opener left', () => {
    expect(backIn(backTo('/?scope=12'), '/')).toBe('/?scope=12')
  })

  it('falls back without one', () => {
    expect(backIn(null, '/')).toBe('/')
    expect(backIn({ back: 3 }, '/')).toBe('/')
  })
})
