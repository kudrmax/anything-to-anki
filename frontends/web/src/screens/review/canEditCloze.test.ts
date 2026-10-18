import { describe, expect, it } from 'vitest'
import type { CardButton, CardState } from '@/api/types'
import { canEditCloze } from './canEditCloze'

const state = (cloze: CardButton['action']): CardState => ({
  decided_here: false,
  decided_elsewhere: 'learn',
  elsewhere: null,
  note: 'decided_on_other_card',
  known_on: null,
  buttons: [
    { button: 'learn', action: null, pressed: false },
    { button: 'cloze', action: cloze, pressed: false },
  ],
})

describe('canEditCloze', () => {
  it('follows what the Cloze button does', () => {
    expect(canEditCloze(state('cloze'))).toBe(true)
  })
  it('is off where the Cloze button does nothing, as on a sibling card of a decided word', () => {
    expect(canEditCloze(state(null))).toBe(false)
  })
})
