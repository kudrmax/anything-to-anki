import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { AVAILABLE, ENTRY, Page, status } from '@/shell/updates/updatesTestKit'
import { Updates } from './UpdatesSection'

describe('Settings — Updates', () => {
  let page: Page

  beforeEach(() => {
    page = new Page()
    vi.spyOn(api, 'getUpdates').mockResolvedValue(status())
  })

  afterEach(() => {
    page.unmount()
    vi.restoreAllMocks()
  })

  it('shows the installed version', async () => {
    await page.render(<Updates />)

    expect(page.text).toContain('Version 1.2.0')
  })

  it('says the copy is on the latest version when the check finds nothing newer', async () => {
    await page.render(<Updates />)

    await page.click('Check for updates')

    expect(api.getUpdates).toHaveBeenLastCalledWith(true)
    expect(page.text).toContain("You're on the latest version (1.2.0)")
    expect(page.dialog()).toBeNull()
  })

  it('opens the update popup when the check finds a newer release', async () => {
    await page.render(<Updates />)
    vi.mocked(api.getUpdates).mockResolvedValue(AVAILABLE)

    await page.click('Check for updates')

    expect(page.dialog()?.getAttribute('aria-label')).toBe('Update available')
  })

  it('tells when the releases could not be reached', async () => {
    await page.render(<Updates />)
    vi.mocked(api.getUpdates).mockResolvedValue(status({ latest: null, check_failed: true }))

    await page.click('Check for updates')

    expect(page.text).toContain("Couldn't check for updates")
  })

  it('opens the whole changelog', async () => {
    vi.spyOn(api, 'getChangelog').mockResolvedValue([ENTRY, { ...ENTRY, version: '1.2.0', summary: 'Older.' }])
    await page.render(<Updates />)

    await page.click('Changelog')

    expect(page.dialog()?.getAttribute('aria-label')).toBe('Changelog')
    expect(page.text).toContain('Updates from inside the app.')
    expect(page.text).toContain('Older.')
  })
})
