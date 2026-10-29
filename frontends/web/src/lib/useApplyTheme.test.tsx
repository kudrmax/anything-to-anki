import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { THEME_HANDLER } from './nativeHost'
import { themeStore, useApplyTheme } from './theme'

function Shell() {
  useApplyTheme()
  return null
}

describe('useApplyTheme', () => {
  let root: Root
  let container: HTMLDivElement
  let systemDark = false
  const mediaListeners = new Set<() => void>()
  const postMessage = vi.fn().mockResolvedValue(null)

  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({
      get matches() { return systemDark },
      addEventListener: (_: string, listener: () => void) => mediaListeners.add(listener),
      removeEventListener: (_: string, listener: () => void) => mediaListeners.delete(listener),
    }))
    Object.assign(window, { webkit: { messageHandlers: { [THEME_HANDLER]: { postMessage } } } })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    themeStore.set('dark')
    postMessage.mockClear()
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    delete (window as { webkit?: unknown }).webkit
    delete document.documentElement.dataset.theme
    vi.unstubAllGlobals()
  })

  it('tells the macOS window the chosen mode before reading the system scheme', () => {
    act(() => root.render(<Shell />))
    expect(postMessage).toHaveBeenCalledWith('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')

    act(() => themeStore.set('system'))
    expect(postMessage).toHaveBeenLastCalledWith('system')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('follows the system scheme while set to system', () => {
    act(() => root.render(<Shell />))
    act(() => themeStore.set('system'))

    systemDark = true
    act(() => mediaListeners.forEach(listener => listener()))

    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
