import { afterEach, describe, expect, it } from 'vitest'
import { clozePanelKey } from './clozeKeys'

const press = (key: string, target: EventTarget | null = document.body, mods = {}) =>
  clozePanelKey({ key, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, repeat: false, target, ...mods })

afterEach(() => {
  document.body.replaceChildren()
})

describe('clozePanelKey', () => {
  it('saves on Enter and cancels on Esc', () => {
    expect(press('Enter')).toBe('save')
    expect(press('Escape')).toBe('cancel')
  })
  it('saves on Enter in the custom hint field', () => {
    expect(press('Enter', document.createElement('input'))).toBe('save')
  })
  it('lets a focused button take Enter itself: clicks never focus buttons, only Tab does', () => {
    const button = document.createElement('button')
    button.append(document.createElement('span'))
    expect(press('Enter', button)).toBeNull()
    expect(press('Enter', button.firstChild)).toBeNull()
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
