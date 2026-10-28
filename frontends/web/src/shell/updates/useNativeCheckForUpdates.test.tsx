import { act } from 'react'
import { useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { CHECK_FOR_UPDATES_EVENT } from '@/lib/nativeHost'
import { AVAILABLE, Page, status } from './updatesTestKit'

function Where() {
  const { pathname, search } = useLocation()
  return <output>{`at ${pathname}${search}`}</output>
}

describe('Check for Updates… in the macOS app menu', () => {
  let page: Page

  beforeEach(async () => {
    page = new Page()
    vi.spyOn(api, 'getUpdates').mockResolvedValue(status())
    await page.render(<Where />, () => {}, '/export')
  })

  afterEach(() => {
    page.unmount()
    vi.restoreAllMocks()
  })

  const chooseMenuItem = () => act(async () => { window.dispatchEvent(new CustomEvent(CHECK_FOR_UPDATES_EVENT)) })

  it('checks past the daily cache and opens the update popup over the current screen', async () => {
    vi.mocked(api.getUpdates).mockResolvedValue(AVAILABLE)

    await chooseMenuItem()

    expect(api.getUpdates).toHaveBeenLastCalledWith(true)
    expect(page.dialog()?.getAttribute('aria-label')).toBe('Update available')
    expect(page.text).toContain('at /export')
    expect(page.text).not.toContain('settings')
  })

  it('says the copy is on the latest version without leaving the screen', async () => {
    await chooseMenuItem()

    expect(page.dialog()?.textContent).toContain("You're on the latest version (1.2.0)")
    expect(page.text).toContain('at /export')

    await page.click('Close')
    expect(page.dialog()).toBeNull()
  })

  it('says when the releases could not be reached', async () => {
    vi.mocked(api.getUpdates).mockResolvedValue(status({ latest: null, check_failed: true }))

    await chooseMenuItem()

    expect(page.dialog()?.textContent).toContain("Couldn't check for updates")
    expect(page.text).toContain('at /export')
  })
})
