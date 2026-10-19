import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CARD_NOTE_LABEL, TIMER_KNOWN_LABEL } from './cardNotes'
import { DecisionButtons } from './PhraseActions'
import { buttons, reviewCard, state } from './reviewFixtures'
import type { ClozeEditor } from './useClozeEditor'
import type { Review } from './useReview'

const REFUSED = { command: null, refused: 'not_decision_card' } as const

describe('DecisionButtons', () => {
  let host: HTMLDivElement
  let root: Root
  let review: Review
  const cloze = { active: false, start: vi.fn(), cancel: vi.fn() } as unknown as ClozeEditor

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
    review = { press: vi.fn() } as unknown as Review
  })

  afterEach(() => act(() => root.unmount()))

  const render = (candidate = reviewCard()) => act(() => root.render(<DecisionButtons candidate={candidate} review={review} cloze={cloze} />))
  const button = (label: string) => [...host.querySelectorAll('button')].find(b => b.textContent?.startsWith(label))!
  const shownNote = () => host.querySelector('[class*="decisionNote"]')?.textContent ?? null

  it('gives a refused button the card note as its tooltip, and the others none', () => {
    render(reviewCard({
      state: state({ note: 'known_elsewhere', buttons: buttons({ learn: { command: null, refused: 'decided_elsewhere' } }) }),
    }))

    expect(button('Learn').title).toBe(CARD_NOTE_LABEL.known_elsewhere)
    expect(button('Learn').disabled).toBe(true)
    expect(button('Skip').title).toBe('')
    expect(button('Skip').disabled).toBe(false)
  })

  it('shows on a card of a word decided on another phrase why its buttons are off', () => {
    render(reviewCard({
      shown: { status: 'known', skipped: false, where: 'other_card' },
      state: state({
        note: 'known_on_other_card',
        buttons: buttons({ learn: REFUSED, cloze: REFUSED, known: { ...REFUSED, pressed: true }, skip: REFUSED }),
      }),
    }))

    expect(shownNote()).toBe('Known via other phrase')
    expect([...host.querySelectorAll('button')].every(b => b.disabled)).toBe(true)
    expect(button('Know').title).toBe('Known via other phrase')
  })

  it('shows the note of a card known by its 30 days in Anki', () => {
    render(reviewCard({
      shown: { status: 'known', skipped: false, where: 'here' },
      state: state({ note: 'known_by_timer', buttons: buttons({ known: { pressed: true } }) }),
    }))

    expect(shownNote()).toBe(TIMER_KNOWN_LABEL)
  })

  it('hands each press to the review with the button the backend gave', () => {
    const card = reviewCard({ state: state({ buttons: buttons({ cloze: { command: 'edit_cloze' } }) }) })
    render(card)

    act(() => button('Cloze').click())
    act(() => button('Learn').click())

    expect(vi.mocked(review.press).mock.calls).toEqual([
      [card.phrase_id, card.state.buttons[1]],
      [card.phrase_id, card.state.buttons[0]],
    ])
  })

  it('does nothing on a refused button', () => {
    render(reviewCard({ state: state({ buttons: buttons({ learn: REFUSED }) }) }))

    act(() => button('Learn').click())

    expect(review.press).not.toHaveBeenCalled()
  })
})
