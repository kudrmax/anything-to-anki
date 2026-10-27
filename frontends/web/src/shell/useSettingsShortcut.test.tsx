import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { OPEN_SETTINGS_EVENT } from '@/lib/nativeHost'
import { useSettingsShortcut } from './useSettingsShortcut'

function Shell() {
  useSettingsShortcut()
  const location = useLocation()
  return <output>{location.pathname}</output>
}

describe('settings shortcut', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
    act(() => root.render(<MemoryRouter initialEntries={['/review']}><Shell /></MemoryRouter>))
  })

  afterEach(() => act(() => root.unmount()))

  const press = (init: KeyboardEventInit) => {
    const event = new KeyboardEvent('keydown', { code: 'Comma', cancelable: true, ...init })
    act(() => { window.dispatchEvent(event) })
    return event
  }

  it('opens settings on ⌘, and keeps the browser from handling it', () => {
    const event = press({ metaKey: true })
    expect(host.textContent).toBe('/settings')
    expect(event.defaultPrevented).toBe(true)
  })

  it('leaves a bare comma alone', () => {
    const event = press({})
    expect(host.textContent).toBe('/review')
    expect(event.defaultPrevented).toBe(false)
  })

  it('opens settings from the macOS app menu', () => {
    act(() => { window.dispatchEvent(new CustomEvent(OPEN_SETTINGS_EVENT)) })
    expect(host.textContent).toBe('/settings')
  })
})
