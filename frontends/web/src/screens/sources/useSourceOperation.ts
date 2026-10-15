import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { RebuildPreview, SourceOperation } from '@/api/types'
import { messageOf } from '@/lib/apiError'

const POLL_INTERVAL_MS = 1000
/** Источник успел занять и отпустить другая операция: итог этой уже не узнать. */
const OVERTAKEN = 'Another operation ran on this source; open the dialog again to see where it stands'

export type OperationRun =
  | { phase: 'idle' }
  | { phase: 'running'; caption: string }
  | { phase: 'done'; operation: SourceOperation }
  | { phase: 'failed'; error: string }

const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

/** Долгая операция над источником: запуск и опрос её состояния, пока backend не скажет, что она закончилась. */
export function useSourceOperation(sourceId: number) {
  const [run, setRun] = useState<OperationRun>({ phase: 'idle' })
  /** Последнее превью Rebuild: остаётся, пока идёт сам Rebuild. */
  const [preview, setPreview] = useState<RebuildPreview | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  const start = useCallback(async (call: () => Promise<SourceOperation>) => {
    try {
      const started = await call()
      if (!alive.current) return
      setRun({ phase: 'running', caption: started.caption })
      for (;;) {
        await pause(POLL_INTERVAL_MS)
        if (!alive.current) return
        const operation = await api.getOperation(sourceId)
        if (!alive.current) return
        if (operation.state === 'running') continue
        if (operation.operation_id !== started.operation_id) {
          setRun({ phase: 'failed', error: OVERTAKEN })
          return
        }
        if (operation.preview) setPreview(operation.preview)
        setRun(operation.state === 'error'
          ? { phase: 'failed', error: operation.error ?? 'The operation failed' }
          : { phase: 'done', operation })
        return
      }
    } catch (e) {
      if (alive.current) setRun({ phase: 'failed', error: messageOf(e) })
    }
  }, [sourceId])

  return { run, preview, start }
}
