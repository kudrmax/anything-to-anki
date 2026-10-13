import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { Scope, SourceBoard } from '@/api/types'
import { isVpnErrorText } from '@/lib/aiErrors'
import { messageOf } from '@/lib/apiError'

const POLL_INTERVAL_MS = 2000
const SEARCH_DELAY_MS = 200
const TOPIC_JOB_TYPE = 'topic_targets'
const NOT_FOUND = '404:'

interface Callbacks {
  onMissingScope: () => void
  onError: (message: string) => void
  /** Что-то изменилось в счётчиках дерева. */
  onChanged: () => void
}

export function useSourceBoard(scope: Scope, query: string, { onMissingScope, onError, onChanged }: Callbacks) {
  const [board, setBoard] = useState<SourceBoard | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setBoard(await api.getSourceBoard(scope, query, signal))
    } catch (e) {
      if (signal?.aborted) return
      if (e instanceof Error && e.message.startsWith(NOT_FOUND)) onMissingScope()
      else onError(messageOf(e))
    }
  }, [scope, query, onMissingScope, onError])

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => void load(controller.signal), query ? SEARCH_DELAY_MS : 0)
    return () => { clearTimeout(timer); controller.abort() }
  }, [load, query])

  const reload = useCallback(async () => { await load(); onChanged() }, [load, onChanged])

  const sources = board?.groups.flatMap(g => g.sources) ?? []
  const anyBusy = sources.some(s => s.status === 'processing' || s.generation_status === 'queued' || s.generation_status === 'running')
  useEffect(() => {
    if (!anyBusy) return
    const timer = setInterval(() => void reload(), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [anyBusy, reload])

  const act = async (call: () => Promise<unknown>) => {
    try {
      await call()
    } catch (e) {
      onError(messageOf(e))
    }
    await reload()
  }

  return {
    board,
    reload,
    process: (id: number) => act(() => api.processSource(id)),
    processPending: () => act(() => api.processPending(scope)),
    processSelected: (ids: number[]) => act(() => api.processSources(ids)),
    deleteSelected: (ids: number[]) => act(async () => {
      const { skipped } = await api.deleteSources(ids)
      if (skipped.length) onError(`${skipped.length} source(s) can't be deleted while processing or built in`)
    }),
    remove: (id: number) => act(() => api.deleteSource(id)),
    rename: (id: number, title: string) => act(() => api.renameSource(id, title)),
    generate: (id: number) => act(() => api.enqueueTopicGeneration(id)),
    cancelGeneration: (id: number) => act(() => api.cancelQueue({ job_type: TOPIC_JOB_TYPE, source_id: id })),
    retryGeneration: (id: number) => act(() => api.retryQueue({ job_type: TOPIC_JOB_TYPE, source_id: id })),
    reprocess: (id: number) => act(() => api.reprocessSource(id)),
    vpnBlocked: sources.some(s => s.generation_status === 'failed' && isVpnErrorText(s.generation_error)),
  }
}
