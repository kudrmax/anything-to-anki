import { describe, expect, it } from 'vitest'
import { keepFocusOnMouseDown } from './mouseFocus'

describe('keepFocusOnMouseDown', () => {
  it('keeps the focus where it was when a button is pressed with the mouse', () => {
    const input = document.createElement('input')
    const button = document.createElement('button')
    document.body.append(input, button)
    input.focus()
    button.addEventListener('mousedown', keepFocusOnMouseDown)
    const event = new MouseEvent('mousedown', { bubbles: true, cancelable: true })
    button.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(input)
    document.body.replaceChildren()
  })
})
