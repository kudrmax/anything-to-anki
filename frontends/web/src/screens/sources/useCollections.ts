import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { Collection, CollectionTree } from '@/api/types'
import { messageOf } from '@/lib/apiError'
import type { UndoOffer } from '@/ui'

interface Callbacks {
  onUndo: (offer: UndoOffer) => void
  onError: (message: string) => void
  /** Источники поменяли место: доска области должна перечитаться. */
  onSourcesMoved: () => void
}

const sourcesWord = (n: number) => (n === 1 ? '1 source' : `${n} sources`)

export function useCollections(props: Callbacks) {
  const [tree, setTree] = useState<CollectionTree | null>(null)
  const callbacks = useRef(props)
  useLayoutEffect(() => {
    callbacks.current = props
  })

  const reload = useCallback(async () => {
    try {
      setTree(await api.getCollectionTree())
    } catch (e) {
      callbacks.current.onError(messageOf(e))
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  const guarded = useCallback(async <T,>(action: () => Promise<T>): Promise<T | null> => {
    try {
      return await action()
    } catch (e) {
      callbacks.current.onError(messageOf(e))
      return null
    } finally {
      await reload()
    }
  }, [reload])

  const create = (name: string, parentId: number | null = null): Promise<Collection | null> =>
    guarded(() => api.createCollection(name, parentId))

  const rename = async (id: number, name: string) => {
    const renamed = await guarded(() => api.renameCollection(id, name))
    if (renamed && renamed.previous_name !== renamed.name) callbacks.current.onUndo({
      message: `Renamed to ${renamed.name}`,
      undo: async () => { await guarded(() => api.renameCollection(id, renamed.previous_name)) },
    })
  }

  const move = async (id: number, parentId: number | null, position: number) => {
    const moved = await guarded(() => api.moveCollection(id, parentId, position))
    if (moved) callbacks.current.onUndo({
      message: 'Collection moved',
      undo: async () => { await guarded(() => api.moveCollection(id, moved.previous_parent_id, moved.previous_position)) },
    })
  }

  const remove = async (id: number): Promise<boolean> => {
    const deleted = await guarded(() => api.deleteCollection(id))
    if (!deleted) return false
    callbacks.current.onSourcesMoved()
    callbacks.current.onUndo({
      message: deleted.evicted_source_count ? `Deleted ${deleted.name} · ${sourcesWord(deleted.evicted_source_count)} kept` : `Deleted ${deleted.name}`,
      undo: async () => { await guarded(() => api.restoreCollection(id)); callbacks.current.onSourcesMoved() },
    })
    return true
  }

  const place = async (sourceIds: number[], collectionId: number | null, targetName: string): Promise<boolean> => {
    const placed = await guarded(() => api.placeSources(sourceIds.map(source_id => ({ source_id, collection_id: collectionId }))))
    if (!placed) return false
    callbacks.current.onSourcesMoved()
    callbacks.current.onUndo({
      message: `Moved ${sourcesWord(sourceIds.length)} to ${targetName}`,
      undo: async () => { await guarded(() => api.placeSources(placed.previous)); callbacks.current.onSourcesMoved() },
    })
    return true
  }

  return { tree, reload, create, rename, move, remove, place }
}
