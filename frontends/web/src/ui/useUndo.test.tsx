import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useUndo } from './useUndo'

function Probe({ onRender }: { onRender: (r: ReturnType<typeof useUndo>) => void }) {
  onRender(useUndo())
  return null
}

describe('useUndo', () => {
  let root: Root
  let latest: ReturnType<typeof useUndo>

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.useFakeTimers()
    root = createRoot(document.createElement('div'))
    act(() => root.render(<Probe onRender={r => { latest = r }} />))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.useRealTimers()
  })

  it('Cmd-Z runs the offer once and clears it', async () => {
    const undo = vi.fn(() => Promise.resolve())
    act(() => latest.show({ message: 'Moved', undo }))
    await act(async () => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', metaKey: true })) })
    await act(async () => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', metaKey: true })) })
    expect(undo).toHaveBeenCalledTimes(1)
    expect(latest.offer).toBeNull()
  })

  it('Cmd-Z leaves the offer alone while a dialog is open', async () => {
    const undo = vi.fn(() => Promise.resolve())
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    document.body.appendChild(dialog)
    act(() => latest.show({ message: 'Moved', undo }))
    await act(async () => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', metaKey: true })) })
    dialog.remove()
    expect(undo).not.toHaveBeenCalled()
    expect(latest.offer).not.toBeNull()
  })

  it('expires', () => {
    act(() => latest.show({ message: 'Moved', undo: () => Promise.resolve() }))
    act(() => { vi.advanceTimersByTime(6000) })
    expect(latest.offer).toBeNull()
  })
})
