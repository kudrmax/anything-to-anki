import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { QueueSnapshot } from '@/api/types'

const POLL_INTERVAL_MS = 2000

interface QueuePollingResult {
  queue: QueueSnapshot | null
  loading: boolean
  refetch: () => Promise<void>
}

/** Polls the queue snapshot while the page is visible. */
export function useQueuePolling(sourceId: number | undefined, queuedLimit: number): QueuePollingResult {
  const [queue, setQueue] = useState<QueueSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const params = useRef({ sourceId, queuedLimit })
  params.current = { sourceId, queuedLimit }

  const refetch = useCallback(async () => {
    try {
      setQueue(await api.getQueue(params.current.sourceId, params.current.queuedLimit))
    } catch {
      // a missed poll is retried on the next tick
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    void refetch()
  }, [refetch, sourceId, queuedLimit])

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null
    const start = () => {
      if (timer === null) timer = setInterval(() => void refetch(), POLL_INTERVAL_MS)
    }
    const stop = () => {
      if (timer !== null) clearInterval(timer)
      timer = null
    }
    const onVisibility = () => {
      if (document.hidden) {
        stop()
      } else {
        void refetch()
        start()
      }
    }
    if (!document.hidden) start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [refetch])

  return { queue, loading, refetch }
}
