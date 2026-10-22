import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import buttonCss from '@/ui/Button.module.css'
import { DecisionButtons, PhraseTools } from './PhraseActions'
import { buttons, reviewCard, state } from './reviewFixtures'
import type { Review } from './useReview'
import css from './review.module.css'

const REFUSED = { command: null, refused: 'not_decision_card' } as const

describe('DecisionButtons', () => {
  let host: HTMLDivElement
  let root: Root
  let review: Review

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
    review = { press: vi.fn(), clozeEditingId: null } as unknown as Review
  })

  afterEach(() => act(() => root.unmount()))

  const render = (candidate = reviewCard()) => act(() => root.render(<DecisionButtons candidate={candidate} review={review} />))
  const button = (label: string) => [...host.querySelectorAll('button')].find(b => b.textContent?.startsWith(label))!

  describe('which button is filled', () => {
    const renderWith = (candidate: ReturnType<typeof reviewCard>, editingId: number | null) => {
      review = { ...review, clozeEditingId: editingId } as Review
      return act(() => root.render(<DecisionButtons candidate={candidate} review={review} />))
    }
    const filled = () => [...host.querySelectorAll('button')]
      .filter(b => b.className.includes(buttonCss.fill)).map(b => b.textContent?.slice(0, 4))

    it('Learn, with the editor closed, whichever is pressed', () => {
      renderWith(reviewCard({ state: state({ buttons: buttons({ known: { pressed: true } }) }) }), null)
      expect(filled()).toEqual(['Lear'])
    })

    it('the one that opened the editor, while the editor is open', () => {
      const card = reviewCard({
        state: state({ buttons: buttons({ learn: { pressed: true }, cloze: { command: 'edit_cloze' } }) }),
      })
      renderWith(card, card.phrase_id)
      expect(filled()).toEqual(['Cloz'])
    })

    it('the pressed one of a cloze card whose markup is being edited', () => {
      const card = reviewCard({
        can_edit_cloze: true,
        state: state({ buttons: buttons({ cloze: { pressed: true } }) }),
      })
      renderWith(card, card.phrase_id)
      expect(filled()).toEqual(['Cloz'])
    })
  })

  it('marks the pressed button as chosen with a check', () => {
    render(reviewCard({ state: state({ buttons: buttons({ known: { pressed: true } }) }) }))

    expect(button('Know').className).toContain(css.chosen)
    expect(button('Know').querySelector('svg')).not.toBeNull()
    expect(button('Learn').className).not.toContain(css.chosen)
    expect(button('Learn').querySelector('svg')).toBeNull()
  })

  it('gives a refused button no tooltip, and writes no line about the card', () => {
    render(reviewCard({
      state: state({ buttons: buttons({ learn: { command: null, refused: 'decided_elsewhere' } }) }),
    }))

    expect(button('Learn').title).toBe('')
    expect(button('Learn').disabled).toBe(true)
    expect(button('Skip').disabled).toBe(false)
    expect(host.textContent).toBe('LearnLClozeCKnowKSkipS')
  })

  it('shows a card of a word decided elsewhere with its status pressed and every button off', () => {
    render(reviewCard({
      shown: { status: 'known', skipped: false, where: 'other_source', tone: 'settled' },
      state: state({
        buttons: buttons({ learn: REFUSED, cloze: REFUSED, known: { ...REFUSED, pressed: true }, skip: REFUSED }),
      }),
    }))

    expect([...host.querySelectorAll('button')].every(b => b.disabled)).toBe(true)
    expect(button('Know').className).toContain(css.chosen)
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

describe('PhraseTools report', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    document.body.append(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  /** Ревью, чья жалоба ответит, когда тест скажет. */
  const reviewWith = () => {
    let answer: (saved: boolean) => void = () => {}
    const report = vi.fn(() => new Promise<boolean>(resolve => { answer = resolve }))
    const review = {
      editing: null, clozeEditingId: null,
      busy: { generating: new Set(), media: new Set(), tts: new Set(), image: new Set() },
      reportReasons: [{ label: 'Bad phrase', picks_words: false }],
      report,
    } as unknown as Review
    return { review, report, answer: (saved: boolean) => answer(saved) }
  }
  const click = (el: Element | undefined) => act(() => { (el as HTMLElement).click() })
  const byText = (text: string) => [...document.querySelectorAll('button, [role="menuitem"], [role="menuitemcheckbox"]')]
    .find(el => el.textContent?.includes(text))
  const menuOpen = () => document.querySelector('[role="menu"]') !== null

  it('#24: closes the menu at once and sends the report in the background', async () => {
    const { review, report, answer } = reviewWith()
    act(() => root.render(<PhraseTools candidate={reviewCard()} review={review} onEditPhrase={() => {}} />))
    click(host.querySelector('[aria-label="Report a problem with this card"]')!)
    click(byText('Bad phrase'))
    click(byText('Send report'))

    expect(menuOpen()).toBe(false)
    expect(report).toHaveBeenCalledWith(1, ['Bad phrase'], '', [])
    await act(async () => { answer(true) })
  })

  it('#24: a report that failed gives back what was chosen', async () => {
    const { review, answer } = reviewWith()
    act(() => root.render(<PhraseTools candidate={reviewCard()} review={review} onEditPhrase={() => {}} />))
    click(host.querySelector('[aria-label="Report a problem with this card"]')!)
    click(byText('Bad phrase'))
    click(byText('Send report'))
    await act(async () => { answer(false) })

    click(host.querySelector('[aria-label="Report a problem with this card"]')!)
    expect(byText('Send report')?.hasAttribute('disabled')).toBe(false)
  })
})
