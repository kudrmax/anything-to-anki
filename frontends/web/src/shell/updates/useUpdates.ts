import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '@/api/client'
import { LONG_OPERATION_STATUS } from '@/api/longOperationSignal'
import type { UpdateStatus, UpdateStep } from '@/api/types'
import { messageOf } from '@/lib/apiError'

// Often enough to reload soon after the server is back, rare enough not to load it.
const POLL_INTERVAL_MS = 2_000
// HTTP Conflict: the backend says an update already runs.
const ALREADY_RUNNING_STATUS = 409

/** Итог явной проверки, когда попап обновления не открылся. */
export type CheckOutcome = 'latest' | 'failed'

/** Обновление, запущенное из приложения: идёт по этапам или упало с концом лога. */
export type UpdateRun = { phase: 'running'; steps: UpdateStep[] } | { phase: 'failed'; logTail: string }

export interface UpdatesState {
  /** Последнее, что backend сказал о релизах; null — ещё не ответил. */
  status: UpdateStatus | null
  checking: boolean
  checkOutcome: CheckOutcome | null
  /** Открыт попап обновления. */
  offerOpen: boolean
  run: UpdateRun | null
  startError: string | null
  /** Проверка мимо суточного кэша; итог, когда попап обновления не открылся, иначе null. */
  checkNow: () => Promise<CheckOutcome | null>
  openOffer: () => void
  closeOffer: () => void
  startUpdate: () => Promise<void>
  dismissFailure: () => void
}

const reloadPage = () => window.location.reload()

/**
 * Что копия знает о новых релизах и как идёт обновление. Пока оно идёт, сервер выключен:
 * неудачные запросы опроса значат «ещё обновляется». Сервер вернулся на другой версии или
 * сказал `done` — страница перечитывается. Страница, открытая посреди обновления, снова
 * показывает его.
 */
export function useUpdatesController(reload: () => void = reloadPage): UpdatesState {
  const [status, setStatus] = useState<UpdateStatus | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkOutcome, setCheckOutcome] = useState<CheckOutcome | null>(null)
  const [offerOpen, setOfferOpen] = useState(false)
  const [run, setRun] = useState<UpdateRun | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const versionBefore = useRef<string | null>(null)

  useEffect(() => {
    api.getUpdates(false).then(setStatus, () => {})
    api.getUpdateState().then(state => { if (state.state === 'running') setRun({ phase: 'running', steps: state.steps }) }, () => {})
  }, [])

  const checkNow = useCallback(async (): Promise<CheckOutcome | null> => {
    setChecking(true)
    setCheckOutcome(null)
    let outcome: CheckOutcome | null
    try {
      const next = await api.getUpdates(true)
      setStatus(next)
      outcome = next.available ? null : next.check_failed ? 'failed' : 'latest'
      if (next.available) setOfferOpen(true)
    } catch {
      outcome = 'failed'
    }
    setCheckOutcome(outcome)
    setChecking(false)
    return outcome
  }, [])

  const current = status?.current ?? null
  const startUpdate = useCallback(async () => {
    setStartError(null)
    versionBefore.current = current
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
    setRun({ phase: 'running', steps: [] })
  }, [current])

  const running = run?.phase === 'running'
  useEffect(() => {
    if (!running) return
    const poll = async () => {
      const [state, version] = await Promise.allSettled([api.getUpdateState(), api.getVersion()])
      const versionNow = version.status === 'fulfilled' ? version.value.version : null
      const changed = versionNow !== null && versionBefore.current !== null && versionNow !== versionBefore.current
      if (changed || (state.status === 'fulfilled' && state.value.state === 'done')) reload()
      else if (state.status === 'fulfilled' && state.value.state === 'failed') setRun({ phase: 'failed', logTail: state.value.log_tail })
      else if (state.status === 'fulfilled' && state.value.state === 'running') setRun({ phase: 'running', steps: state.value.steps })
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

export const UpdatesContext = createContext<UpdatesState | null>(null)

export function useUpdates(): UpdatesState {
  const updates = useContext(UpdatesContext)
  if (!updates) throw new Error('useUpdates needs an UpdatesProvider')
  return updates
}
