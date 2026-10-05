import { describe, expect, it } from 'vitest'
import { pastedPicture } from './pastedPicture'

const clipboardWith = (...files: File[]) => ({ files } as unknown as DataTransfer)
const picture = new File(['png'], 'image.png', { type: 'image/png' })
const text = new File(['hi'], 'note.txt', { type: 'text/plain' })

describe('pastedPicture', () => {
  it('returns the picture from the clipboard', () => {
    expect(pastedPicture({ clipboardData: clipboardWith(text, picture), target: document.body })).toBe(picture)
  })

  it('ignores a clipboard without pictures', () => {
    expect(pastedPicture({ clipboardData: clipboardWith(text), target: document.body })).toBeNull()
    expect(pastedPicture({ clipboardData: null, target: document.body })).toBeNull()
  })

  it('leaves pastes into a text field alone', () => {
    const input = document.createElement('textarea')
    expect(pastedPicture({ clipboardData: clipboardWith(picture), target: input })).toBeNull()
  })

  it('stays out of the way while a dialog is open', () => {
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    document.body.append(dialog)
    try {
      expect(pastedPicture({ clipboardData: clipboardWith(picture), target: document.body })).toBeNull()
    } finally {
      dialog.remove()
    }
  })
})
