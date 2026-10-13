import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SourceSummary } from '@/api/types'
import { SourceRow } from './SourceRow'

const source: SourceSummary = {
  id: 7, title: 'Pilot', status: 'done', kind: 'text', role: 'content', has_video: false, source_url: null,
  video_downloaded: false, created_at: '2026-10-01T00:00:00Z', candidate_count: 4, learn_count: 0, decided_count: 0,
  processing_stage: null, collection_id: 11, collection_path: ['Friends', 'Season 1'], stage: 'ready',
  awaiting_generation: false, generation_status: null, generation_error: null, is_permanent: false,
}

describe('SourceRow', () => {
  let host: HTMLDivElement
  let root: Root
  const onReview = vi.fn()
  const noop = () => {}

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onReview.mockReset()
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const render = (takenBySelection: boolean, showPath = false) => act(() => root.render(
    <SourceRow
      source={source} selected={false} showPath={showPath} primary={false}
      onProcess={noop} onGenerate={noop} onCancelGeneration={noop} onRetryGeneration={noop}
      onReview={onReview} onExport={noop} onDelete={noop} onRename={noop} onReprocess={noop}
      onRowClick={() => takenBySelection} onMoveTo={noop} dragIds={() => [source.id]}
    />,
  ))
  const row = () => host.firstElementChild as HTMLElement

  it('opens the source on a plain click', () => {
    render(false)
    act(() => row().click())
    expect(onReview).toHaveBeenCalledWith(7)
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
})
