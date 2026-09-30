import { describe, expect, it } from 'vitest'
import { reviewAction } from './hotkeys'

const press = (key: string, target: EventTarget | null = document.body, mods = {}) =>
  reviewAction({ key, metaKey: false, ctrlKey: false, altKey: false, repeat: false, target, ...mods })

describe('reviewAction', () => {
  it('maps keys to actions', () => {
    expect(press('ArrowDown')).toBe('next')
    expect(press('ArrowUp')).toBe('prev')
    expect(press('1')).toBe('learn')
    expect(press('2')).toBe('known')
    expect(press('3')).toBe('skip')
    expect(press(' ')).toBe('audio')
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
