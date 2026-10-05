import { describe, expect, it } from 'vitest'
import type { CandidateCloze } from '@/api/types'
import { decisionChange, learnConvertsCloze } from './decision'

const CLOZE: CandidateCloze = { hidden_word_indices: [1], hint_kind: 'none', custom_hint: null }

describe('decisionChange', () => {
  it('applies a new decision', () => {
    expect(decisionChange('pending', 'learn')).toBe('learn')
    expect(decisionChange('learn', 'skip')).toBe('skip')
  })
  it('undoes the decision when it is chosen again', () => {
    expect(decisionChange('known', 'known')).toBe('pending')
  })
  it('turns a cloze card back into a plain Learn card instead of undoing it', () => {
    expect(decisionChange('learn', 'learn', true)).toBe('learn')
    expect(decisionChange('learn', 'skip', true)).toBe('skip')
  })
})

describe('learnConvertsCloze', () => {
  it('converts a cloze card that is not in Anki yet', () => {
    expect(learnConvertsCloze({ cloze: CLOZE, can_cloze: true })).toBe(true)
  })
  it('leaves an exported cloze card as it is: Learn toggles as usual', () => {
    expect(learnConvertsCloze({ cloze: CLOZE, can_cloze: false })).toBe(false)
  })
  it('has nothing to convert on a plain card', () => {
    expect(learnConvertsCloze({ cloze: null, can_cloze: true })).toBe(false)
  })
})
