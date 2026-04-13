import { useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { AnkiStatus } from '@/api/types'

const POLL_INTERVAL_MS = 5_000

/**
 * Polls GET /anki/status so the UI reacts automatically
 * when Anki is launched or closed — no page refresh needed.
 */
export function useAnkiStatus(): AnkiStatus | null {
  const [status, setStatus] = useState<AnkiStatus | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false

    const check = async () => {
      try {
        const s = await api.getAnkiStatus()
        if (!cancelled) setStatus(s)
      } catch {
        if (!cancelled) setStatus({ available: false, version: null })
      }
    }

    void check()
    timerRef.current = setInterval(() => void check(), POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      if (timerRef.current !== null) clearInterval(timerRef.current)
    }
  }, [])

  return status
}
