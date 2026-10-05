import { describe, expect, it } from 'vitest'
import type { ClozePreview } from '@/api/types'
import { clozeSaveRequest } from './clozeDraft'

const PREVIEW: ClozePreview = {
  phrase: 'She gave up smoking.',
  words: [],
  hidden_word_indices: [1, 2],
  hint_kind: 'none',
  custom_hint: null,
  front: 'She […] smoking.',
  hint: '',
  available_hints: ['none'],
  can_save: true,
}

describe('clozeSaveRequest', () => {
  it('sends the phrase the words were picked in', () => {
    expect(clozeSaveRequest({ hidden_word_indices: [2], hint_kind: 'custom', custom_hint: 'quit' }, PREVIEW)).toEqual({
      phrase: 'She gave up smoking.', hidden_word_indices: [2], hint_kind: 'custom', custom_hint: 'quit',
    })
  })
})
