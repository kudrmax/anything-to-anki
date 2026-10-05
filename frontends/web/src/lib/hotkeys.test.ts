import { describe, expect, it } from 'vitest'
import { allowedInClozeMarkup, reviewAction } from './hotkeys'

const press = (key: string, target: EventTarget | null = document.body, mods = {}) =>
  reviewAction({ key, metaKey: false, ctrlKey: false, altKey: false, repeat: false, target, ...mods })

describe('reviewAction', () => {
  it('maps keys to actions', () => {
    expect(press('ArrowDown')).toBe('next')
    expect(press('ArrowUp')).toBe('prev')
    expect(press(' ')).toBe('audio')
  })
  it('maps decision keys 1-4 in order', () => {
    expect(press('1')).toBe('learn')
    expect(press('2')).toBe('cloze')
    expect(press('3')).toBe('known')
    expect(press('4')).toBe('skip')
  })
  it('ignores other keys', () => {
    expect(press('a')).toBeNull()
  })
  it('ignores keys typed into inputs, textareas and editable elements', () => {
    expect(press('1', document.createElement('input'))).toBeNull()
    expect(press(' ', document.createElement('textarea'))).toBeNull()
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    expect(press('2', editable)).toBeNull()
  })
  it('ignores keys inside a menu or dialog', () => {
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    const inner = document.createElement('button')
    dialog.appendChild(inner)
    expect(press('3', inner)).toBeNull()
  })
  it('leaves Space to a focused button', () => {
    expect(press(' ', document.createElement('button'))).toBeNull()
    expect(press('1', document.createElement('button'))).toBe('learn')
  })
  it('ignores keys while any menu or dialog is open, wherever the focus is', () => {
    const menu = document.createElement('div')
    menu.setAttribute('role', 'menu')
    document.body.appendChild(menu)
    try {
      expect(press('1')).toBeNull()
      expect(press('ArrowDown')).toBeNull()
    } finally {
      menu.remove()
    }
    expect(press('1')).toBe('learn')
  })
  it('does not repeat a decision or audio while the key is held', () => {
    expect(press('1', document.body, { repeat: true })).toBeNull()
    expect(press(' ', document.body, { repeat: true })).toBeNull()
    expect(press('ArrowDown', document.body, { repeat: true })).toBe('next')
  })
  it('ignores key combinations with modifiers', () => {
    expect(press('1', document.body, { metaKey: true })).toBeNull()
  })
})

describe('allowedInClozeMarkup', () => {
  it('lets decisions and audio through while markup mode is open', () => {
    expect(allowedInClozeMarkup('learn')).toBe(true)
    expect(allowedInClozeMarkup('known')).toBe(true)
    expect(allowedInClozeMarkup('skip')).toBe(true)
    expect(allowedInClozeMarkup('audio')).toBe(true)
  })
  it('keeps the card in place while markup mode is open', () => {
    expect(allowedInClozeMarkup('prev')).toBe(false)
    expect(allowedInClozeMarkup('next')).toBe(false)
    expect(allowedInClozeMarkup('cloze')).toBe(false)
  })
})
