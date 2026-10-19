import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import buttonCss from '@/ui/Button.module.css'
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

  describe('which button is lit', () => {
    const editing = { active: true, start: vi.fn(), cancel: vi.fn() } as unknown as ClozeEditor
    const renderWith = (candidate: ReturnType<typeof reviewCard>, editor: ClozeEditor) =>
      act(() => root.render(<DecisionButtons candidate={candidate} review={review} cloze={editor} />))
    const lit = () => [...host.querySelectorAll('button')]
      .filter(b => b.className.includes(buttonCss.fill)).map(b => b.textContent?.slice(0, 4))

    it('the pressed one, with the editor closed', () => {
      renderWith(reviewCard({ state: state({ buttons: buttons({ learn: { pressed: true } }) }) }), cloze)
      expect(lit()).toEqual(['Lear'])
    })

    it('the one that opened the editor, not the pressed one, while the editor is open', () => {
      renderWith(reviewCard({
        state: state({ buttons: buttons({ learn: { pressed: true }, cloze: { command: 'edit_cloze' } }) }),
      }), editing)
      expect(lit()).toEqual(['Cloz'])
    })

    it('the pressed one of a cloze card whose markup is being edited', () => {
      renderWith(reviewCard({
        can_edit_cloze: true,
        state: state({ buttons: buttons({ cloze: { pressed: true } }) }),
      }), editing)
      expect(lit()).toEqual(['Cloz'])
    })
  })

  it('gives a refused button no tooltip, and writes no line about the card', () => {
    render(reviewCard({
      state: state({ buttons: buttons({ learn: { command: null, refused: 'decided_elsewhere' } }) }),
    }))

    expect(button('Learn').title).toBe('')
    expect(button('Learn').disabled).toBe(true)
    expect(button('Skip').disabled).toBe(false)
    expect(host.textContent).toBe('Learn1Cloze2Know3Skip4')
  })

  it('shows a card of a word decided elsewhere with its status pressed and every button off', () => {
    render(reviewCard({
      shown: { status: 'known', skipped: false, where: 'other_source', tone: 'settled' },
      state: state({
        buttons: buttons({ learn: REFUSED, cloze: REFUSED, known: { ...REFUSED, pressed: true }, skip: REFUSED }),
      }),
    }))

    expect([...host.querySelectorAll('button')].every(b => b.disabled)).toBe(true)
    expect(button('Know').className).toContain(buttonCss.fill)
    expect(button('Know').title).toBe('')
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
