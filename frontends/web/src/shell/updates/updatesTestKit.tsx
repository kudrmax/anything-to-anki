import type { ReactNode } from 'react'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { api } from '@/api/client'
import type { ChangelogEntry, UpdateStatus } from '@/api/types'
import { UpdatesProvider } from './UpdatesProvider'

export const ENTRY: ChangelogEntry = {
  version: '1.3.0',
  released_on: '2026-10-20',
  summary: 'Updates from inside the app.',
  sections: [{ title: 'New', html: '<ul><li>An <strong>Update</strong> button</li></ul>' }],
}

export const status = (changes: Partial<UpdateStatus> = {}): UpdateStatus => ({
  current: '1.2.0', latest: '1.2.0', available: false, entries: [], check_failed: false, ...changes,
})

export const AVAILABLE = status({ latest: '1.3.0', available: true, entries: [ENTRY] })

/** Страница в тесте: корень в документе, чтобы портал модалки был виден через document.body. */
export class Page {
  private readonly host: HTMLDivElement
  private readonly root: Root

  constructor() {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    this.host = document.body.appendChild(document.createElement('div'))
    this.root = createRoot(this.host)
    vi.spyOn(api, 'getUpdateState').mockResolvedValue({ state: 'idle', log_tail: '' })
  }

  async render(children: ReactNode, reload: () => void = () => {}, path = '/'): Promise<void> {
    await act(async () => this.root.render(
      <MemoryRouter initialEntries={[path]}>
        <UpdatesProvider reload={reload}>{children}</UpdatesProvider>
      </MemoryRouter>,
    ))
  }

  get text(): string {
    return document.body.textContent ?? ''
  }

  dialog(): HTMLElement | null {
    return document.body.querySelector<HTMLElement>('[role=dialog]')
  }

  button(label: string): HTMLButtonElement | undefined {
    return [...document.body.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === label)
  }

  async click(label: string): Promise<void> {
    const button = this.button(label)
    if (!button) throw new Error(`No button «${label}» in: ${this.text}`)
    await act(async () => button.click())
  }

  unmount(): void {
    act(() => this.root.unmount())
    this.host.remove()
  }
}
