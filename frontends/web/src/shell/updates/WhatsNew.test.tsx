import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { WhatsNew } from './WhatsNew'
import { ENTRY, Page } from './updatesTestKit'

describe("What's new", () => {
  let page: Page

  beforeEach(() => {
    page = new Page()
    vi.spyOn(api, 'markChangelogSeen').mockResolvedValue()
  })

  afterEach(() => {
    page.unmount()
    vi.restoreAllMocks()
  })

  it('shows the versions released since the last one seen and marks them seen on close', async () => {
    vi.spyOn(api, 'getUnseenChangelog').mockResolvedValue([ENTRY])
    await page.render(<WhatsNew />)

    expect(page.dialog()?.getAttribute('aria-label')).toBe("What's new")
    expect(page.text).toContain('Updates from inside the app.')
    expect(api.markChangelogSeen).not.toHaveBeenCalled()

    await page.click('Close')

    expect(page.dialog()).toBeNull()
    expect(api.markChangelogSeen).toHaveBeenCalledTimes(1)
  })

  it('stays away when nothing new was released', async () => {
    vi.spyOn(api, 'getUnseenChangelog').mockResolvedValue([])
    await page.render(<WhatsNew />)

    expect(page.dialog()).toBeNull()
  })

  it('closes quietly when marking seen is refused', async () => {
    vi.spyOn(api, 'getUnseenChangelog').mockResolvedValue([ENTRY])
    vi.mocked(api.markChangelogSeen).mockRejectedValue(new Error('423: busy'))
    await page.render(<WhatsNew />)

    await page.click('Close')

    expect(page.dialog()).toBeNull()
    expect(page.text).not.toContain('busy')
  })
})
