import { describe, expect, it } from 'vitest'
import { allowedInClozeMarkup, isToolAction, reviewAction } from './hotkeys'

const press = (code: string, target: EventTarget | null = document.body, mods = {}) =>
  reviewAction({ code, metaKey: false, ctrlKey: false, altKey: false, repeat: false, target, ...mods })

describe('reviewAction', () => {
  it('moves between phrases with any arrow', () => {
    expect(press('ArrowDown')).toBe('next')
    expect(press('ArrowRight')).toBe('next')
    expect(press('ArrowUp')).toBe('prev')
    expect(press('ArrowLeft')).toBe('prev')
  })
  it('maps decisions to the first letters of their names', () => {
    expect(press('KeyL')).toBe('learn')
    expect(press('KeyC')).toBe('cloze')
    expect(press('KeyK')).toBe('known')
    expect(press('KeyS')).toBe('skip')
  })
  it('learns on Space too', () => {
    expect(press('Space')).toBe('learn')
  })
  it('plays audio on A', () => {
    expect(press('KeyA')).toBe('audio')
  })
  it('maps the card tools', () => {
    expect(press('KeyI')).toBe('image')
    expect(press('KeyE')).toBe('edit')
    expect(press('KeyR')).toBe('regenerate')
    expect(press('KeyF')).toBe('report')
  })
  it('ignores the old digit keys and other keys', () => {
    expect(press('Digit1')).toBeNull()
    expect(press('KeyZ')).toBeNull()
  })
  it('ignores keys typed into inputs, textareas and editable elements', () => {
    expect(press('KeyL', document.createElement('input'))).toBeNull()
    expect(press('Space', document.createElement('textarea'))).toBeNull()
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    expect(press('KeyC', editable)).toBeNull()
  })
  it('ignores keys inside a menu or dialog', () => {
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    const inner = document.createElement('button')
    dialog.appendChild(inner)
    expect(press('KeyK', inner)).toBeNull()
  })
  it('leaves Space to a focused button', () => {
    expect(press('Space', document.createElement('button'))).toBeNull()
    expect(press('KeyL', document.createElement('button'))).toBe('learn')
  })
  it('ignores keys while any menu or dialog is open, wherever the focus is', () => {
    const menu = document.createElement('div')
    menu.setAttribute('role', 'menu')
    document.body.appendChild(menu)
    try {
      expect(press('KeyL')).toBeNull()
      expect(press('ArrowDown')).toBeNull()
    } finally {
      menu.remove()
    }
    expect(press('KeyL')).toBe('learn')
  })
  it('does not repeat a decision, audio or tool while the key is held', () => {
    expect(press('KeyL', document.body, { repeat: true })).toBeNull()
    expect(press('KeyA', document.body, { repeat: true })).toBeNull()
    expect(press('KeyI', document.body, { repeat: true })).toBeNull()
    expect(press('ArrowRight', document.body, { repeat: true })).toBe('next')
  })
  it('ignores key combinations with modifiers', () => {
    expect(press('KeyL', document.body, { metaKey: true })).toBeNull()
    expect(press('KeyC', document.body, { metaKey: true })).toBeNull()
  })
})

describe('isToolAction', () => {
  it('tells the card tools from decisions and moves', () => {
    expect(isToolAction('image')).toBe(true)
    expect(isToolAction('report')).toBe(true)
    expect(isToolAction('learn')).toBe(false)
    expect(isToolAction('next')).toBe(false)
  })
})

describe('allowedInClozeMarkup', () => {
  it('lets decisions and audio through while markup mode is open', () => {
    expect(allowedInClozeMarkup('learn')).toBe(true)
    expect(allowedInClozeMarkup('known')).toBe(true)
    expect(allowedInClozeMarkup('skip')).toBe(true)
    expect(allowedInClozeMarkup('audio')).toBe(true)
  })
  it('keeps the card and its tools in place while markup mode is open', () => {
    expect(allowedInClozeMarkup('prev')).toBe(false)
    expect(allowedInClozeMarkup('next')).toBe(false)
    expect(allowedInClozeMarkup('cloze')).toBe(false)
    expect(allowedInClozeMarkup('edit')).toBe(false)
  })
})
