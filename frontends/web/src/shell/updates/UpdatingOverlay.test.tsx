import { act } from 'react'
import { useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '@/api/client'
import type { UpdateRunProgress } from '@/api/types'
import { CHECK_FOR_UPDATES_EVENT } from '@/lib/nativeHost'
import { UpdateIndicator } from './UpdateIndicator'
import { AVAILABLE, Page, status } from './updatesTestKit'

const POLL_MS = 2_000
const running: UpdateRunProgress = { state: 'running', log_tail: '' }
const failed: UpdateRunProgress = { state: 'failed', log_tail: 'make: *** [update] Error 1' }

describe('updating', () => {
  let page: Page
  const reload = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    reload.mockReset()
    page = new Page()
    vi.spyOn(api, 'getUpdates').mockResolvedValue(AVAILABLE)
    vi.spyOn(api, 'startUpdate').mockResolvedValue()
    vi.spyOn(api, 'getUpdateState').mockResolvedValue(running)
    vi.spyOn(api, 'getVersion').mockResolvedValue({ version: '1.2.0' })
  })

  afterEach(() => {
    page.unmount()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  const startUpdate = async () => {
    await page.render(<UpdateIndicator />, reload)
    await page.click('Update available')
    await page.click('Update')
  }
  const tick = () => act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS) })

  it('covers the app while the server restarts and waits through refused requests', async () => {
    await startUpdate()
    expect(page.text).toContain('Updating…')

    vi.mocked(api.getUpdateState).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.mocked(api.getVersion).mockRejectedValue(new TypeError('Failed to fetch'))
    await tick()
    await tick()

    expect(page.text).toContain('Updating…')
    expect(reload).not.toHaveBeenCalled()
  })

  it('reloads the page once the server is back on the new version', async () => {
    await startUpdate()

    vi.mocked(api.getVersion).mockResolvedValue({ version: '1.3.0' })
    await tick()

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('goes on waiting for an update that is already running', async () => {
    vi.mocked(api.startUpdate).mockRejectedValue(new ApiError(409, '{"detail":"running"}'))
    await startUpdate()

    expect(page.text).toContain('Updating…')
  })

  it('shows why the update failed and the command to run it by hand', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await startUpdate()

    vi.mocked(api.getUpdateState).mockResolvedValue(failed)
    await tick()

    expect(page.text).not.toContain('Updating…')
    expect(page.text).toContain('make: *** [update] Error 1')
    expect(page.text).toContain('make update')
    await page.click('Copy')
    expect(writeText).toHaveBeenCalledWith('make update')
    expect(page.button('Copied')).toBeDefined()

    await page.click('Close')
    expect(page.text).not.toContain('Error 1')
  })
})

describe('Check for Updates… in the macOS app menu', () => {
  let page: Page

  function Where() {
    return <output>{useLocation().search}</output>
  }

  beforeEach(() => {
    page = new Page()
  })

  afterEach(() => {
    page.unmount()
    vi.restoreAllMocks()
  })

  it('checks right away, past the daily cache, from any screen', async () => {
    vi.spyOn(api, 'getUpdates').mockResolvedValue(status())
    await page.render(<Where />, () => {}, '/export')

    vi.mocked(api.getUpdates).mockResolvedValue(AVAILABLE)
    await act(async () => { window.dispatchEvent(new CustomEvent(CHECK_FOR_UPDATES_EVENT)) })

    expect(api.getUpdates).toHaveBeenLastCalledWith(true)
    expect(page.dialog()?.getAttribute('aria-label')).toBe('Update available')
  })

  it('opens the Updates settings to say the copy is on the latest version', async () => {
    vi.spyOn(api, 'getUpdates').mockResolvedValue(status())
    await page.render(<Where />, () => {}, '/export')

    await act(async () => { window.dispatchEvent(new CustomEvent(CHECK_FOR_UPDATES_EVENT)) })

    expect(page.text).toContain('section=updates')
  })
})
