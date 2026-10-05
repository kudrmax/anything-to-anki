import { afterEach, describe, expect, it, vi } from 'vitest'
import { clozePanelKey } from './clozeKeys'

const press = (key: string, target: EventTarget | null = document.body, mods = {}) =>
  clozePanelKey({ key, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, repeat: false, target, ...mods })

const button = (focusVisible: boolean) => {
  const el = document.createElement('button')
  const matches = el.matches.bind(el)
  vi.spyOn(el, 'matches').mockImplementation(selector => (selector === ':focus-visible' ? focusVisible : matches(selector)))
  document.body.append(el)
  return el
}

afterEach(() => {
  document.body.replaceChildren()
  vi.restoreAllMocks()
})

describe('clozePanelKey', () => {
  it('saves on Enter and cancels on Esc', () => {
    expect(press('Enter')).toBe('save')
    expect(press('Escape')).toBe('cancel')
  })
  it('saves on Enter in the custom hint field', () => {
    expect(press('Enter', document.createElement('input'))).toBe('save')
  })
  it('saves on Enter after a word was clicked with the mouse', () => {
    expect(press('Enter', button(false))).toBe('save')
  })
  it('lets a button focused from the keyboard take Enter itself', () => {
    expect(press('Enter', button(true))).toBeNull()
  })
  it('leaves Enter and Esc to the phrase textarea', () => {
    const textarea = document.createElement('textarea')
    expect(press('Enter', textarea)).toBeNull()
    expect(press('Escape', textarea)).toBeNull()
  })
  it('ignores modified and repeated keys', () => {
    expect(press('Enter', document.body, { shiftKey: true })).toBeNull()
    expect(press('Enter', document.body, { repeat: true })).toBeNull()
  })
  it('ignores keys while a menu or dialog is open', () => {
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    document.body.append(dialog)
    expect(press('Enter')).toBeNull()
  })
})
