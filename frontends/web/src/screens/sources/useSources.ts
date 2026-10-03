import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { Collection, SourceSummary, Stats } from '@/api/types'
import { isVpnErrorText } from '@/lib/aiErrors'

const POLL_INTERVAL_MS = 2000
const TOPIC_JOB_TYPE = 'topic_targets'

/** Источник, который можно обработать: тему сначала нужно сгенерировать. */
const isPending = (s: SourceSummary): boolean => (s.status === 'new' || s.status === 'error') && !s.awaiting_generation

interface Loaded {
  sources: SourceSummary[]
  stats: Stats
  collections: Collection[]
}

const fetchAll = async (): Promise<Loaded> => {
  const [sources, stats, collections] = await Promise.all([api.listSources(), api.getStats(), api.listCollections()])
  return { sources, stats, collections }
}

export function useSources() {
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [collections, setCollections] = useState<Collection[]>([])
  const [processingAll, setProcessingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      const loaded = await fetchAll()
      setSources(loaded.sources)
      setStats(loaded.stats)
      setCollections(loaded.collections)
    } catch {
      // ignore background reload errors
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  // Один опрос всего списка, пока хоть один источник обрабатывается или ждёт AI.
  const anyBusy = sources.some(s => s.status === 'processing' || s.generation_status === 'queued' || s.generation_status === 'running')
  useEffect(() => {
    if (!anyBusy) return
    const timer = setInterval(() => void reload(), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [anyBusy, reload])

  const markProcessing = (id: number) =>
    setSources(prev => prev.map(s => (s.id === id ? { ...s, status: 'processing' as const } : s)))

  const process = async (id: number) => {
    try {
      await api.processSource(id)
      markProcessing(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start processing')
    }
  }

  const runGeneration = async (call: () => Promise<unknown>, fallback: string) => {
    try {
      await call()
    } catch (e) {
      setError(e instanceof Error ? e.message : fallback)
    }
    await reload()
  }

  const generate = (id: number) => runGeneration(() => api.enqueueTopicGeneration(id), 'Failed to queue generation')
  const cancelGeneration = (id: number) => runGeneration(() => api.cancelQueue(TOPIC_JOB_TYPE, id), 'Failed to cancel generation')
  const retryGeneration = (id: number) => runGeneration(() => api.retryQueue(TOPIC_JOB_TYPE, id), 'Failed to retry generation')

  const processAll = async () => {
    const pending = sources.filter(isPending)
    if (pending.length === 0) return
    setProcessingAll(true)
    try {
      for (const source of pending) {
        try {
          await api.processSource(source.id)
          markProcessing(source.id)
        } catch {
          // skip individual errors, continue with others
        }
      }
    } finally {
      setProcessingAll(false)
    }
  }

  const remove = async (id: number) => {
    if (!window.confirm('Delete this source and all its candidates?')) return
    try {
      await api.deleteSource(id)
      setSources(prev => prev.filter(s => s.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete source')
    }
  }

  const rename = async (id: number, title: string) => {
    try {
      await api.renameSource(id, title)
      setSources(prev => prev.map(s => (s.id === id ? { ...s, title } : s)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to rename source')
    }
  }

  const assignCollection = async (sourceId: number, collectionId: number | null) => {
    try {
      await api.assignSourceCollection(sourceId, collectionId)
      void reload()
    } catch {
      // ignore
    }
  }

  const reprocess = (id: number) =>
    api.reprocessSource(id)
      .then(() => reload())
      .catch((e: Error) => console.error('Reprocess failed:', e))

  const createCollection = async (name: string) => {
    try {
      await api.createCollection(name)
      void reload()
    } catch {
      // ignore
    }
  }

  const renameCollection = async (id: number, name: string) => {
    try {
      await api.renameCollection(id, name)
      void reload()
    } catch {
      // ignore
    }
  }

  const deleteCollection = async (id: number): Promise<boolean> => {
    const collection = collections.find(c => c.id === id)
    if (!collection) return false
    if (!confirm(`Delete "${collection.name}"? The ${collection.source_count} source(s) will become uncategorized.`)) return false
    try {
      await api.deleteCollection(id)
      void reload()
      return true
    } catch {
      return false
    }
  }

  const prepend = (source: SourceSummary) => setSources(prev => [source, ...prev])
  const pendingCount = sources.filter(isPending).length
  const vpnBlocked = sources.some(s => s.generation_status === 'failed' && isVpnErrorText(s.generation_error))

  return {
    sources, stats, collections, error, clearError: () => setError(null), pendingCount, processingAll, vpnBlocked,
    reload, prepend, process, processAll, generate, cancelGeneration, retryGeneration, remove, rename, assignCollection, reprocess,
    createCollection, renameCollection, deleteCollection,
  }
}
