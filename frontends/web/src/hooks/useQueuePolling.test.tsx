import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { QueueSnapshot } from '@/api/types'
import { useQueuePolling } from './useQueuePolling'

const snapshot = (totalQueued: number): QueueSnapshot => ({
  counts: [], total_queued: totalQueued, total_running: 0, total_failed: 0, running: [], queued: [], failed: [],
})

interface PendingRead {
  signal: AbortSignal | undefined
  resolve: (queue: QueueSnapshot) => void
}

function Probe({ onRender }: { onRender: (result: ReturnType<typeof useQueuePolling>) => void }) {
  onRender(useQueuePolling(undefined, 20))
  return null
}

describe('useQueuePolling', () => {
  let reads: PendingRead[]
  let root: Root
  let latest: ReturnType<typeof useQueuePolling>

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    reads = []
    vi.spyOn(api, 'getQueue').mockImplementation((_sourceId, _limit, signal) => new Promise((resolve, reject) => {
      signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
      reads.push({ signal, resolve })
    }))
    root = createRoot(document.createElement('div'))
    act(() => root.render(<Probe onRender={result => { latest = result }} />))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.restoreAllMocks()
  })

  it('aborts the read still in flight when a new one starts', async () => {
    const refetched = act(() => latest.refetch())

    expect(reads[0].signal?.aborted).toBe(true)
    await act(async () => reads[1].resolve(snapshot(1)))
    await refetched
    expect(latest.queue?.total_queued).toBe(1)
  })

  it('a late answer to the aborted read never replaces the fresh queue', async () => {
    const refetched = act(() => latest.refetch())
    await act(async () => reads[1].resolve(snapshot(1)))
    await refetched

    await act(async () => reads[0].resolve(snapshot(2)))

    expect(latest.queue?.total_queued).toBe(1)
  })

  it('aborts the read in flight on unmount', () => {
    act(() => root.unmount())
    root = createRoot(document.createElement('div'))

    expect(reads[0].signal?.aborted).toBe(true)
  })
})
