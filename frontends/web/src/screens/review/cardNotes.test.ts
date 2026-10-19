import { describe, expect, it } from 'vitest'
import { CARD_NOTE_LABEL, cardNoteText } from './cardNotes'

describe('cardNoteText', () => {
  it('shows no label when the backend gives no note', () => {
    expect(cardNoteText({ note: null, known_on: null })).toBeNull()
  })

  it('shows the label of the note as given', () => {
    expect(cardNoteText({ note: 'learn_elsewhere', known_on: null })).toBe('Learn in another source')
  })

  it.each([
    ['learned_on_other_card', 'Learned via other phrase'],
    ['known_on_other_card', 'Known via other phrase'],
  ] as const)('labels a card decided on another phrase: %s', (note, label) => {
    expect(cardNoteText({ note, known_on: null })).toBe(label)
  })

  it('adds the day the card turns Known when the backend gives it', () => {
    const day = new Date('2026-11-17T12:00:00Z').toLocaleDateString()
    expect(cardNoteText({ note: 'in_anki', known_on: '2026-11-17T12:00:00Z' })).toBe(`${CARD_NOTE_LABEL.in_anki} · Known on ${day}`)
  })
})
