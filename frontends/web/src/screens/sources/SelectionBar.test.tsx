import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SelectionBar } from './SelectionBar'

describe('SelectionBar', () => {
  let host: HTMLDivElement
  let root: Root
  const handlers = { onMoveTo: vi.fn(), onProcess: vi.fn(), onDelete: vi.fn(), onClear: vi.fn() }

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    Object.values(handlers).forEach(h => h.mockReset())
    host = document.createElement('div')
    root = createRoot(host)
    act(() => root.render(<SelectionBar count={3} {...handlers} />))
  })

  afterEach(() => act(() => root.unmount()))

  const button = (label: string) =>
    [...host.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent === label || b.getAttribute('aria-label') === label)!

  it('shows the count', () => {
    expect(host.textContent).toContain('3 selected')
  })

  it.each([
    ['Move to…', 'onMoveTo'],
    ['Process', 'onProcess'],
    ['Delete', 'onDelete'],
    ['Clear selection', 'onClear'],
  ] as const)('%s fires %s', (label, handler) => {
    act(() => button(label).click())
    expect(handlers[handler]).toHaveBeenCalledTimes(1)
  })
})
