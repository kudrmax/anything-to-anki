import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { CollectionTree } from '@/api/types'
import type { UndoOffer } from '@/ui'
import { useCollections } from './useCollections'

const counts = { total: 0, reviewed: 0, pending: 0 }
const emptyTree: CollectionTree = { all: counts, unsorted: counts, collections: [] }

const onUndo = vi.fn<(offer: UndoOffer) => void>()
const onError = vi.fn<(message: string) => void>()
const onSourcesMoved = vi.fn<() => void>()

function Probe({ onRender }: { onRender: (result: ReturnType<typeof useCollections>) => void }) {
  onRender(useCollections({ onUndo: o => onUndo(o), onError: m => onError(m), onSourcesMoved: () => onSourcesMoved() }))
  return null
}

describe('useCollections', () => {
  let root: Root
  let latest: ReturnType<typeof useCollections>

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onUndo.mockReset()
    onError.mockReset()
    onSourcesMoved.mockReset()
    vi.spyOn(api, 'getCollectionTree').mockResolvedValue(emptyTree)
    root = createRoot(document.createElement('div'))
    act(() => root.render(<Probe onRender={result => { latest = result }} />))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.restoreAllMocks()
  })

  it('place offers an undo that restores the placements the backend returned', async () => {
    const previous = [{ source_id: 1, collection_id: 7 }, { source_id: 2, collection_id: null }]
    const placeSources = vi.spyOn(api, 'placeSources').mockResolvedValue({ previous })

    await act(async () => latest.place([1, 2], 5, 'Music'))

    expect(placeSources).toHaveBeenCalledWith([{ source_id: 1, collection_id: 5 }, { source_id: 2, collection_id: 5 }])
    expect(onUndo).toHaveBeenCalledTimes(1)
    const offer = onUndo.mock.calls[0][0]
    expect(offer.message).toBe('Moved 2 sources to Music')

    await act(async () => offer.undo())

    expect(placeSources).toHaveBeenLastCalledWith(previous)
  })

  it('remove offers an undo that restores the collection', async () => {
    vi.spyOn(api, 'deleteCollection').mockResolvedValue({ id: 3, name: 'Films', evicted_source_count: 1 })
    const restore = vi.spyOn(api, 'restoreCollection').mockResolvedValue({ id: 3, name: 'Films', parent_id: null, position: 0 })

    let removed = false
    await act(async () => { removed = await latest.remove(3) })

    expect(removed).toBe(true)
    const offer = onUndo.mock.calls[0][0]
    expect(offer.message).toBe('Deleted Films · 1 source kept')

    await act(async () => offer.undo())

    expect(restore).toHaveBeenCalledWith(3)
  })

  it('an undo that fails reports the error instead of rejecting', async () => {
    vi.spyOn(api, 'deleteCollection').mockResolvedValue({ id: 3, name: 'Films', evicted_source_count: 0 })
    vi.spyOn(api, 'restoreCollection').mockRejectedValue(new Error('409: name taken'))

    await act(async () => { await latest.remove(3) })
    await act(async () => onUndo.mock.calls[0][0].undo())

    expect(onError).toHaveBeenCalled()
  })

  it('fresh inline callbacks on every render do not refetch the tree', async () => {
    const getTree = vi.spyOn(api, 'getCollectionTree')
    getTree.mockClear()
    await act(async () => root.render(<Probe onRender={result => { latest = result }} />))
    await act(async () => root.render(<Probe onRender={result => { latest = result }} />))

    expect(getTree).not.toHaveBeenCalled()
  })
})
