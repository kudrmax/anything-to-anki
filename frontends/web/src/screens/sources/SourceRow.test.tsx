import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SourceSummary } from '@/api/types'
import { SourceRow } from './SourceRow'

const source: SourceSummary = {
  id: 7, title: 'Pilot', status: 'done', kind: 'text', role: 'content', has_video: false, source_url: null,
  video_downloaded: false, created_at: '2026-10-01T00:00:00Z', candidate_count: 4, learn_count: 0, progress: { decided: 0, total: 4 },
  processing_stage: null, collection_id: 11, collection_path: ['Friends', 'Season 1'], stage: 'ready',
  awaiting_generation: false, generation_status: null, generation_error: null, available_operation: null, busy_with: null, operation_hint: null,
  can_review: true, can_export: false, can_delete: true, review_fraction: 0,
}

describe('SourceRow', () => {
  let host: HTMLDivElement
  let root: Root
  const onReview = vi.fn()
  const onLongPress = vi.fn()
  const noop = () => {}

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onReview.mockReset()
    onLongPress.mockReset()
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const render = (takenBySelection: boolean, showPath = false, shown: SourceSummary = source) => act(() => root.render(
    <SourceRow
      source={shown} selected={false} showPath={showPath} primary={false}
      onProcess={noop} onGenerate={noop} onCancelGeneration={noop} onRetryGeneration={noop}
      onReview={onReview} onExport={noop} onDelete={noop} onRename={noop} onRebuild={noop} onRefresh={noop}
      onRowClick={() => takenBySelection} onMoveTo={noop} dragIds={() => [source.id]}
      draggable onLongPress={onLongPress}
    />,
  ))
  const row = () => host.firstElementChild as HTMLElement

  it('opens the source on a plain click', () => {
    render(false)
    act(() => row().click())
    expect(onReview).toHaveBeenCalledWith(7)
  })

  it('opens only a source the backend lets review', () => {
    render(false, false, { ...source, can_review: false })
    act(() => row().click())
    expect(onReview).not.toHaveBeenCalled()
  })

  it('shows how far the review is as the backend says', () => {
    render(false, false, { ...source, status: 'reviewed', review_fraction: 0.25 })
    expect(host.innerHTML).toContain('--p: 25%')
  })

  it('does not open the source when the click was taken by selection', () => {
    render(true)
    act(() => row().click())
    expect(onReview).not.toHaveBeenCalled()
  })

  it('shows the node name only when asked', () => {
    render(false)
    expect(host.textContent).not.toContain('Season 1')
    render(false, true)
    expect(host.textContent).toContain('Season 1')
  })

  const touch = (type: string) => act(() => {
    const event = new MouseEvent(type, { bubbles: true })
    Object.defineProperty(event, 'pointerType', { value: 'touch' })
    row().dispatchEvent(event)
  })

  it('is an option of the list', () => {
    render(false)
    expect(row().getAttribute('role')).toBe('option')
    expect(row().getAttribute('aria-selected')).toBe('false')
  })

  it('starts selection on a long tap and does not open the source', () => {
    vi.useFakeTimers()
    try {
      render(false)
      touch('pointerdown')
      act(() => { vi.advanceTimersByTime(600) })
      touch('pointerup')
      act(() => row().click())
      expect(onLongPress).toHaveBeenCalledWith(7)
      expect(onReview).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('treats a short tap as a click', () => {
    vi.useFakeTimers()
    try {
      render(false)
      touch('pointerdown')
      act(() => { vi.advanceTimersByTime(100) })
      touch('pointerup')
      act(() => { vi.advanceTimersByTime(1000) })
      act(() => row().click())
      expect(onLongPress).not.toHaveBeenCalled()
      expect(onReview).toHaveBeenCalledWith(7)
    } finally {
      vi.useRealTimers()
    }
  })
})
