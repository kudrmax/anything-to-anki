import { act } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from '@/api/client'
import type { UpdateRunProgress } from '@/api/types'
import { UpdateIndicator } from './UpdateIndicator'
import { AVAILABLE, Page, RESTART_COMMAND, UPDATE_COMMAND } from './updatesTestKit'

const POLL_MS = 2_000
const LOG_HEIGHT = 480
const running: UpdateRunProgress = { state: 'running', log_tail: '', steps: [] }
const failed: UpdateRunProgress = { state: 'failed', log_tail: 'make: *** [update] Error 1', steps: [] }
const installing: UpdateRunProgress = {
  state: 'running',
  log_tail: '',
  steps: [
    { title: 'Downloading v1.3.0', status: 'done' },
    { title: 'Installing v1.3.0', status: 'current' },
    { title: 'Starting the new version', status: 'pending' },
  ],
}
const startFailed: UpdateRunProgress = {
  state: 'running',
  log_tail: '',
  steps: [
    { title: 'Downloading v1.3.0', status: 'done' },
    { title: 'Installing v1.3.0', status: 'done' },
    { title: 'Starting the new version', status: 'failed' },
  ],
}

const stepItems = () => [...document.body.querySelectorAll<HTMLElement>('[aria-label="Update steps"] li')]
const steps = () => stepItems().map(item => [item.textContent, item.dataset.status])
const step = (title: string) => stepItems().find(item => item.textContent === title)

describe('updating', () => {
  let page: Page
  const reload = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    reload.mockReset()
    page = new Page()
    vi.spyOn(api, 'getUpdates').mockResolvedValue(AVAILABLE)
    vi.spyOn(api, 'startUpdate').mockResolvedValue()
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
    vi.mocked(api.getUpdateState).mockResolvedValue(running)
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

  it('shows each stage of the update and which one runs now', async () => {
    await startUpdate()

    vi.mocked(api.getUpdateState).mockResolvedValue(installing)
    await tick()

    expect(steps()).toEqual([
      ['Downloading v1.3.0', 'done'],
      ['Installing v1.3.0', 'current'],
      ['Starting the new version', 'pending'],
    ])
    expect(step('Installing v1.3.0')?.querySelector('[role=status]')).not.toBeNull()
    expect(step('Downloading v1.3.0')?.querySelector('svg')).not.toBeNull()
    expect(step('Starting the new version')?.querySelector('svg, [role=status]')).toBeNull()
  })

  it('marks the stage that failed', async () => {
    await startUpdate()

    vi.mocked(api.getUpdateState).mockResolvedValue(startFailed)
    await tick()

    expect(steps()).toEqual([
      ['Downloading v1.3.0', 'done'],
      ['Installing v1.3.0', 'done'],
      ['Starting the new version', 'failed'],
    ])
    expect(step('Starting the new version')?.querySelector('svg')).not.toBeNull()
  })

  it('keeps the last stage it got while the server does not answer', async () => {
    await startUpdate()
    vi.mocked(api.getUpdateState).mockResolvedValue(installing)
    await tick()

    vi.mocked(api.getUpdateState).mockRejectedValue(new TypeError('Failed to fetch'))
    await tick()

    expect(steps()[1]).toEqual(['Installing v1.3.0', 'current'])
  })

  it('says from the start how to restart the app by hand if the update hangs', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await startUpdate()

    expect(page.text).toContain('Nothing has changed for 10 minutes?')
    expect(page.text).toContain('Open the Terminal app')
    expect(page.text).toContain(RESTART_COMMAND)
    await page.click('Copy')
    expect(writeText).toHaveBeenCalledWith(RESTART_COMMAND)
  })

  it('shows the update again when the page opens while it runs', async () => {
    vi.mocked(api.getUpdateState).mockResolvedValue(running)

    await page.render(<UpdateIndicator />, reload)

    expect(page.text).toContain('Updating…')
  })

  it('does not show a finished or failed update when the page opens', async () => {
    vi.mocked(api.getUpdateState).mockResolvedValue(failed)

    await page.render(<UpdateIndicator />, reload)

    expect(page.text).not.toContain('Updating…')
    expect(page.text).not.toContain('Update failed')
  })

  it('reloads the page once the server is back on the new version', async () => {
    await startUpdate()

    vi.mocked(api.getVersion).mockResolvedValue({ version: '1.3.0' })
    await tick()

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('reloads the page once the update is done, even on the same version', async () => {
    await startUpdate()

    vi.mocked(api.getUpdateState).mockResolvedValue({ state: 'done', log_tail: '', steps: [] })
    await tick()

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('keeps the popup and says why the update did not start', async () => {
    vi.mocked(api.startUpdate).mockRejectedValue(new ApiError(500, '{"detail":"Uncommitted changes"}'))
    await startUpdate()

    expect(page.dialog()?.getAttribute('aria-label')).toBe('Update available')
    expect(page.dialog()?.textContent).toContain('Uncommitted changes')
    expect(page.text).not.toContain('Updating…')
  })

  it('keeps the popup while a long operation refuses the update', async () => {
    vi.mocked(api.startUpdate).mockRejectedValue(new ApiError(423, '{"detail":"busy"}'))
    await startUpdate()

    expect(page.dialog()?.getAttribute('aria-label')).toBe('Update available')
    expect(page.text).not.toContain('Updating…')
  })

  it('goes on waiting for an update that is already running', async () => {
    vi.mocked(api.startUpdate).mockRejectedValue(new ApiError(409, '{"detail":"running"}'))
    await startUpdate()

    expect(page.text).toContain('Updating…')
  })

  it('shows why the update failed and the command to run it by hand', async () => {
    const scrolledTo = vi.fn()
    vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(LOG_HEIGHT)
    vi.spyOn(HTMLElement.prototype, 'scrollTop', 'set').mockImplementation(scrolledTo)
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await startUpdate()

    vi.mocked(api.getUpdateState).mockResolvedValue(failed)
    await tick()

    expect(page.text).not.toContain('Updating…')
    expect(page.text).toContain('make: *** [update] Error 1')
    expect(page.text).toContain('Open the Terminal app')
    expect(page.text).toContain(UPDATE_COMMAND)
    expect(scrolledTo).toHaveBeenLastCalledWith(LOG_HEIGHT)
    await page.click('Copy')
    expect(writeText).toHaveBeenCalledWith(UPDATE_COMMAND)
    expect(page.button('Copied')).toBeDefined()

    await page.click('Close')
    expect(page.text).not.toContain('Error 1')
  })

  it('says when the command could not be copied', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await startUpdate()
    vi.mocked(api.getUpdateState).mockResolvedValue(failed)
    await tick()

    await page.click('Copy')

    expect(page.button('Copy failed')).toBeDefined()
  })
})
