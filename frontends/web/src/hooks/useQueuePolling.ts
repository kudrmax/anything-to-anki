import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { QueueFailed, QueueGlobalSummary, QueueOrder } from '@/api/types'

const POLL_INTERVAL_MS = 2000

interface QueuePollingResult {
  summary: QueueGlobalSummary | null
  order: QueueOrder | null
  failed: QueueFailed | null
  loading: boolean
  refetch: () => void
}

export function useQueuePolling(sourceId?: number): QueuePollingResult {
  const [summary, setSummary] = useState<QueueGlobalSummary | null>(null)
  const [order, setOrder] = useState<QueueOrder | null>(null)
  const [failed, setFailed] = useState<QueueFailed | null>(null)
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sourceIdRef = useRef(sourceId)
  sourceIdRef.current = sourceId

  const fetchAll = useCallback(async () => {
    const sid = sourceIdRef.current
    try {
      const [s, o, f] = await Promise.all([
        api.getQueueGlobalSummary(sid),
        api.getQueueOrder(sid, 50),
        api.getQueueFailed(sid),
      ])
      setSummary(s)
      setOrder(o)
      setFailed(f)
    } catch {
      // ignore poll errors
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    void fetchAll()

    intervalRef.current = setInterval(() => {
      void fetchAll()
    }, POLL_INTERVAL_MS)

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [fetchAll, sourceId])

  return { summary, order, failed, loading, refetch: fetchAll }
}
