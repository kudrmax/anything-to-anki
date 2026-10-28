import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '@/api/client'
import { LONG_OPERATION_STATUS } from '@/api/longOperationSignal'
import type { UpdateStatus } from '@/api/types'
import { messageOf } from '@/lib/apiError'

const POLL_INTERVAL_MS = 2_000
const ALREADY_RUNNING_STATUS = 409

/** Итог явной проверки, когда попап обновления не открылся. */
export type CheckOutcome = 'latest' | 'failed'

/** Обновление, запущенное из приложения: идёт или упало с концом лога. */
export type UpdateRun = { phase: 'running' } | { phase: 'failed'; logTail: string }

export interface Updates {
  /** Последнее, что backend сказал о релизах; null — ещё не ответил. */
  status: UpdateStatus | null
  checking: boolean
  checkOutcome: CheckOutcome | null
  /** Открыт попап обновления. */
  offerOpen: boolean
  run: UpdateRun | null
  startError: string | null
  checkNow: () => Promise<void>
  openOffer: () => void
  closeOffer: () => void
  startUpdate: () => Promise<void>
  dismissFailure: () => void
}

const reloadPage = () => window.location.reload()

/**
 * Что копия знает о новых релизах и как идёт обновление. Пока оно идёт, сервер выключен:
 * неудачные запросы опроса значат «ещё обновляется». Сервер вернулся на другой версии или
 * сказал `done` — страница перечитывается.
 */
export function useUpdatesController(reload: () => void = reloadPage): Updates {
  const [status, setStatus] = useState<UpdateStatus | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkOutcome, setCheckOutcome] = useState<CheckOutcome | null>(null)
  const [offerOpen, setOfferOpen] = useState(false)
  const [run, setRun] = useState<UpdateRun | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const versionBefore = useRef<string | null>(null)

  useEffect(() => {
    api.getUpdates(false).then(setStatus, () => {})
  }, [])

  const checkNow = useCallback(async () => {
    setChecking(true)
    setCheckOutcome(null)
    try {
      const next = await api.getUpdates(true)
      setStatus(next)
      if (next.available) setOfferOpen(true)
      else setCheckOutcome(next.check_failed ? 'failed' : 'latest')
    } catch {
      setCheckOutcome('failed')
    } finally {
      setChecking(false)
    }
  }, [])

  const startUpdate = useCallback(async () => {
    setStartError(null)
    versionBefore.current = status?.current ?? null
    try {
      await api.startUpdate()
    } catch (error) {
      const code = error instanceof ApiError ? error.status : null
      if (code === LONG_OPERATION_STATUS) return
      if (code !== ALREADY_RUNNING_STATUS) {
        setStartError(messageOf(error))
        return
      }
    }
    setOfferOpen(false)
    setRun({ phase: 'running' })
  }, [status])

  const running = run?.phase === 'running'
  useEffect(() => {
    if (!running) return
    const poll = async () => {
      const [state, version] = await Promise.allSettled([api.getUpdateState(), api.getVersion()])
      const versionNow = version.status === 'fulfilled' ? version.value.version : null
      const changed = versionNow !== null && versionBefore.current !== null && versionNow !== versionBefore.current
      if (changed || (state.status === 'fulfilled' && state.value.state === 'done')) reload()
      else if (state.status === 'fulfilled' && state.value.state === 'failed') setRun({ phase: 'failed', logTail: state.value.log_tail })
    }
    const timer = setInterval(() => void poll(), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [running, reload])

  return {
    status,
    checking,
    checkOutcome,
    offerOpen,
    run,
    startError,
    checkNow,
    openOffer: useCallback(() => setOfferOpen(true), []),
    closeOffer: useCallback(() => { setOfferOpen(false); setStartError(null) }, []),
    startUpdate,
    dismissFailure: useCallback(() => setRun(null), []),
  }
}

export const UpdatesContext = createContext<Updates | null>(null)

export function useUpdates(): Updates {
  const updates = useContext(UpdatesContext)
  if (!updates) throw new Error('useUpdates needs an UpdatesProvider')
  return updates
}
