import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopePicker } from './ScopePicker'

describe('ScopePicker', () => {
  let host: HTMLDivElement
  let root: Root
  const onOpen = vi.fn()
  const onClose = vi.fn()

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onOpen.mockReset()
    onClose.mockReset()
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  const render = (open: boolean) => act(() => root.render(
    <ScopePicker title="Season 1" open={open} onOpen={onOpen} onClose={onClose}>
      <button type="button" role="treeitem">Friends</button>
    </ScopePicker>,
  ))

  it('asks to open from the scope button', () => {
    render(false)
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
    act(() => host.querySelector('button')!.click())
    expect(onOpen).toHaveBeenCalled()
  })

  it('leaves closing to the screen: picking a node does not close the sheet by itself', () => {
    render(true)
    act(() => document.body.querySelector<HTMLElement>('[role="treeitem"]')!.click())
    expect(onClose).not.toHaveBeenCalled()
    act(() => [...document.body.querySelectorAll('button')].find(b => b.textContent === 'Close')!.click())
    expect(onClose).toHaveBeenCalled()
  })
})
