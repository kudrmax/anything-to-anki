import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { Scope, SourceBoard } from '@/api/types'
import { isVpnErrorText } from '@/lib/aiErrors'
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

export function useSourceBoard(scope: Scope, query: string, props: Callbacks) {
  const [board, setBoard] = useState<SourceBoard | null>(null)
  const [boardKey, setBoardKey] = useState<string | null>(null)
  const callbacks = useRef(props)
  useLayoutEffect(() => {
    callbacks.current = props
  })
  const inFlight = useRef<AbortController | null>(null)

  /** Только последний запрос вправе обновить доску; фоновые опросы молчат об ошибках. */
  const key = `${String(scope)}\u0000${query}`
  const load = useCallback(async (quiet = false) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const loaded = await api.getSourceBoard(scope, query, controller.signal)
      if (!controller.signal.aborted) { setBoard(loaded); setBoardKey(key) }
    } catch (e) {
      if (controller.signal.aborted) return
      if (e instanceof Error && e.message.startsWith(NOT_FOUND)) callbacks.current.onMissingScope()
      else if (!quiet) callbacks.current.onError(messageOf(e))
    } finally {
      if (inFlight.current === controller) inFlight.current = null
    }
  }, [scope, query, key])

  useEffect(() => {
    const timer = setTimeout(() => void load(), query ? SEARCH_DELAY_MS : 0)
    return () => { clearTimeout(timer); inFlight.current?.abort() }
  }, [load, query])

  const reload = useCallback(async () => { await load(); callbacks.current.onChanged() }, [load])

  const sources = board?.groups.flatMap(g => g.sources) ?? []
  const anyBusy = sources.some(s => s.status === 'processing' || s.generation_status === 'queued' || s.generation_status === 'running')
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
    board,
    /** На экране ещё прошлая область: новая грузится, пустого кадра не бывает. */
    stale: board !== null && boardKey !== key,
    reload,
    process: (id: number) => act(() => api.processSource(id)),
    processPending: () => start(() => api.processPending(scope)),
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
    rebuild: (id: number) => act(() => api.rebuildSource(id, false)),
    vpnBlocked: sources.some(s => s.generation_status === 'failed' && isVpnErrorText(s.generation_error)),
  }
}
