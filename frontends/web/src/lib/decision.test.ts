import { describe, expect, it } from 'vitest'
import { decisionChange } from './decision'

describe('decisionChange', () => {
  it('applies a new decision', () => {
    expect(decisionChange('pending', 'learn')).toBe('learn')
    expect(decisionChange('learn', 'skip')).toBe('skip')
  })
  it('does nothing when the phrase already has this decision (the API cannot return it to pending)', () => {
    expect(decisionChange('known', 'known')).toBeNull()
  })
})
