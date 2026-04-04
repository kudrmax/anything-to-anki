import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { SourceSummary } from '@/api/types'

const POLL_INTERVAL_MS = 2000

export function useSourcePolling(
  sourceId: number | null,
  onDone: (source: SourceSummary) => void,
) {
  const [isPolling, setIsPolling] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stop = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const start = useCallback(
    (id: number) => {
      stop()
      setIsPolling(true)
      intervalRef.current = setInterval(() => {
        api
          .listSources()
          .then((sources) => {
            const source = sources.find((s) => s.id === id)
            if (!source) return
            if (source.status !== 'processing') {
              stop()
              onDone(source)
            }
          })
          .catch(() => stop())
      }, POLL_INTERVAL_MS)
    },
    [stop, onDone],
  )

  useEffect(() => {
    return () => stop()
  }, [stop])

  return { isPolling: isPolling && sourceId !== null, start, stop }
}
