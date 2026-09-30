import { describe, expect, it } from 'vitest'
import { decisionChange } from './decision'

describe('decisionChange', () => {
  it('applies a new decision', () => {
    expect(decisionChange('pending', 'learn')).toBe('learn')
    expect(decisionChange('learn', 'skip')).toBe('skip')
  })
  it('undoes the decision when it is chosen again', () => {
    expect(decisionChange('known', 'known')).toBe('pending')
  })
})
