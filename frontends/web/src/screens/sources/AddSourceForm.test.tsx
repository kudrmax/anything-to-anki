import { act, useEffect } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { DetectedFormat } from '@/api/types'
import { droppedFiles } from '@/lib/nativeHost'
import { AddSourceForm } from './AddSourceForm'

const DROPPED = '/books/novel.epub'

const seen: { state: unknown; location: string } = { state: undefined, location: '' }
function LocationProbe() {
  const current = useLocation()
  useEffect(() => {
    seen.state = current.state
    seen.location = current.pathname + current.search
  }, [current])
  return null
}

describe('AddSourceForm', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.spyOn(api, 'detectFormat').mockResolvedValue({ format: 'epub' } as DetectedFormat)
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
    vi.restoreAllMocks()
  })

  it('takes dropped paths into the field and clears them from history', async () => {
    await act(async () => root.render(
      <MemoryRouter initialEntries={[{ pathname: '/add', search: '?x=1', state: droppedFiles([DROPPED]) }]}>
        <AddSourceForm onReload={() => Promise.resolve()} onToast={() => {}} />
        <LocationProbe />
      </MemoryRouter>,
    ))

    expect(host.querySelector<HTMLTextAreaElement | HTMLInputElement>('textarea, input')!.value).toBe(DROPPED)
    expect(seen.state).toBeNull()
    expect(seen.location).toBe('/add?x=1')
  })
})
