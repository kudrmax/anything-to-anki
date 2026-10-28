import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { UpdateIndicator } from './UpdateIndicator'
import { AVAILABLE, Page, status } from './updatesTestKit'

describe('UpdateIndicator', () => {
  let page: Page

  beforeEach(() => {
    page = new Page()
  })

  afterEach(() => {
    page.unmount()
    vi.restoreAllMocks()
  })

  it('stays hidden while the copy is on the latest release', async () => {
    vi.spyOn(api, 'getUpdates').mockResolvedValue(status())

    await page.render(<UpdateIndicator />)

    expect(api.getUpdates).toHaveBeenCalledWith(false)
    expect(page.text).not.toContain('Update available')
  })

  it('opens the changes of the new release with an Update button', async () => {
    vi.spyOn(api, 'getUpdates').mockResolvedValue(AVAILABLE)
    await page.render(<UpdateIndicator />)

    await page.click('Update available')

    expect(page.dialog()?.getAttribute('aria-label')).toBe('Update available')
    expect(page.text).toContain('1.3.0')
    expect(page.text).toContain('Updates from inside the app.')
    expect(page.dialog()?.querySelector('h3')?.textContent).toBe('New')
    expect(page.dialog()?.querySelector('strong')?.textContent).toBe('Update')
    expect(page.button('Update')).toBeDefined()
  })

  it('stays after the popup is closed', async () => {
    vi.spyOn(api, 'getUpdates').mockResolvedValue(AVAILABLE)
    await page.render(<UpdateIndicator />)

    await page.click('Update available')
    await page.click('Close')

    expect(page.dialog()).toBeNull()
    expect(page.button('Update available')).toBeDefined()
  })
})
