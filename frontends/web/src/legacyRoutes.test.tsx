import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { OldSourceExport, OldSourceReview } from './legacyRoutes'

function Where() {
  const location = useLocation()
  return <output>{location.pathname + location.search}</output>
}

describe('old source bookmarks', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const open = (path: string) => act(() => root.render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/sources/:id/review" element={<OldSourceReview />} />
        <Route path="/sources/:id/export" element={<OldSourceExport />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  ))

  it.each([
    ['/sources/7/review', '/review?scope=source-7'],
    ['/sources/7/review?candidate=42', '/review?scope=source-7&candidate=42'],
    ['/sources/7/export', '/export?scope=source-7'],
  ])('%s → %s', (from, to) => {
    open(from)
    expect(host.textContent).toBe(to)
  })
})
