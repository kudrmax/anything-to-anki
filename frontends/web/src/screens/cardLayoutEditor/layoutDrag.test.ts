import { describe, expect, it } from 'vitest'
import { editFor, type DropTarget } from './layoutDrag'

const LINE = { x: 0, y: 0, width: 0, height: 0 }
const gap = (column: number, row: number): DropTarget => ({ kind: 'gap', column, row, line: LINE })
const join = (column: number, row: number, position: number): DropTarget => ({ kind: 'join', column, row, position, line: LINE })
const TRAY: DropTarget = { kind: 'tray' }

describe('editFor', () => {
  it('puts a block into a new row or next to other blocks', () => {
    const block = { kind: 'block', element: 'tts', placed: true } as const
    expect(editFor(block, gap(1, 2))).toEqual({ kind: 'move_block', element: 'tts', column: 1, row: 2, position: null })
    expect(editFor(block, join(0, 3, 1))).toEqual({ kind: 'move_block', element: 'tts', column: 0, row: 3, position: 1 })
  })

  it('hides a placed block dropped on the tray, and leaves a hidden one hidden', () => {
    expect(editFor({ kind: 'block', element: 'tts', placed: true }, TRAY)).toEqual({ kind: 'hide_block', element: 'tts' })
    expect(editFor({ kind: 'block', element: 'tts', placed: false }, TRAY)).toBeNull()
  })

  it('moves a divider between rows and removes it on the tray', () => {
    const divider = { kind: 'divider', column: 0, row: 1 } as const
    expect(editFor(divider, gap(1, 0))).toEqual({ kind: 'move_row', column: 0, row: 1, to_column: 1, to_row: 0 })
    expect(editFor(divider, TRAY)).toEqual({ kind: 'remove_divider', column: 0, row: 1 })
    expect(editFor(divider, join(0, 0, 0))).toBeNull()
  })

  it('adds a new divider only between rows', () => {
    expect(editFor({ kind: 'new-divider' }, gap(0, 2))).toEqual({ kind: 'insert_divider', column: 0, row: 2 })
    expect(editFor({ kind: 'new-divider' }, TRAY)).toBeNull()
  })
})
