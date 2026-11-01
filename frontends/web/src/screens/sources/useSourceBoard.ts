import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { onLongOperationFinished } from '@/api/longOperationSignal'
import { api } from '@/api/client'
import type { RecentBoard, Scope, SourceBoard, SourceSummary, SourcesView } from '@/api/types'
import { messageOf } from '@/lib/apiError'

const POLL_INTERVAL_MS = 2000
const SEARCH_DELAY_MS = 200
const TOPIC_JOB_TYPE = 'topic_targets'
const NOT_FOUND = '404:'

const sourcesWord = (n: number) => (n === 1 ? '1 source' : `${n} sources`)

interface Callbacks {
  onMissingScope: () => void
  onError: (message: string) => void
  /** Что-то изменилось в счётчиках дерева. */
  onChanged: () => void
}

/** Источники на экране: группы доски области или строки Recent. */
function sourcesOf(loaded: SourceBoard | RecentBoard | null): SourceSummary[] {
  if (!loaded) return []
  if ('groups' in loaded) return loaded.groups.flatMap(g => g.sources)
  return loaded.items.flatMap(item => (item.kind === 'source' ? [item.source] : []))
}

export function useSourceBoard(view: SourcesView, query: string, props: Callbacks) {
  const [loaded, setLoaded] = useState<SourceBoard | RecentBoard | null>(null)
  const [boardKey, setBoardKey] = useState<string | null>(null)
  const callbacks = useRef(props)
  useLayoutEffect(() => {
    callbacks.current = props
  })
  const inFlight = useRef<AbortController | null>(null)

  /** Только последний запрос вправе обновить доску; фоновые опросы молчат об ошибках. */
  const key = `${String(view)}\u0000${query}`
  const load = useCallback(async (quiet = false) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const next = view === 'recent'
        ? await api.getRecent(query, controller.signal)
        : await api.getSourceBoard(view, query, controller.signal)
      if (!controller.signal.aborted) { setLoaded(next); setBoardKey(key) }
    } catch (e) {
      if (controller.signal.aborted) return
      if (e instanceof Error && e.message.startsWith(NOT_FOUND)) callbacks.current.onMissingScope()
      else if (!quiet) callbacks.current.onError(messageOf(e))
    } finally {
      if (inFlight.current === controller) inFlight.current = null
    }
  }, [view, query, key])

  useEffect(() => {
    const timer = setTimeout(() => void load(), query ? SEARCH_DELAY_MS : 0)
    return () => { clearTimeout(timer); inFlight.current?.abort() }
  }, [load, query])

  const reload = useCallback(async () => { await load(); callbacks.current.onChanged() }, [load])

  /** Долгая операция над источниками закончилась: доска показывает её итог. */
  useEffect(() => onLongOperationFinished(() => void reload()), [reload])

  const sources = sourcesOf(loaded)
  const anyBusy = sources.some(s => s.busy_with !== null || s.generation_status === 'queued' || s.generation_status === 'running')
  useEffect(() => {
    if (!anyBusy) return
    const timer = setInterval(() => {
      if (inFlight.current) return
      void load(true).then(() => callbacks.current.onChanged())
    }, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [anyBusy, load])

  const act = async (call: () => Promise<unknown>) => {
    try {
      await call()
    } catch (e) {
      callbacks.current.onError(messageOf(e))
    }
    await reload()
  }

  const start = (call: () => Promise<{ skipped: number[] }>) => act(async () => {
    const { skipped } = await call()
    if (skipped.length) callbacks.current.onError(`${sourcesWord(skipped.length)} can't be processed right now`)
  })

  return {
    board: loaded && 'groups' in loaded ? loaded : null,
    recent: loaded && 'items' in loaded ? loaded : null,
    /** На экране ещё прошлый раздел: новый грузится, пустого кадра не бывает. */
    stale: loaded !== null && boardKey !== key,
    reload,
    process: (id: number) => act(() => api.processSource(id)),
    processPending: (scope: Scope) => start(() => api.processPending(scope)),
    processSelected: (ids: number[]) => start(() => api.processSources(ids)),
    deleteSelected: (ids: number[]) => act(async () => {
      const { skipped } = await api.deleteSources(ids)
      if (skipped.length) callbacks.current.onError(`${skipped.length} source(s) can't be deleted while processing or built in`)
    }),
    remove: (id: number) => act(() => api.deleteSource(id)),
    rename: (id: number, title: string) => act(() => api.renameSource(id, title)),
    generate: (id: number) => act(() => api.enqueueTopicGeneration(id)),
    cancelGeneration: (id: number) => act(() => api.cancelQueue({ job_type: TOPIC_JOB_TYPE, source_id: id })),
    retryGeneration: (id: number) => act(() => api.retryQueue({ job_type: TOPIC_JOB_TYPE, source_id: id })),
  }
}
