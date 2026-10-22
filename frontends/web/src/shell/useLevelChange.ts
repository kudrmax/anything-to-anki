import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import { onLevelChange } from '@/api/levelChangeSignal'
import type { LevelChangeStatus } from '@/api/types'

const POLL_INTERVAL_MS = 1_000

const reloadPage = () => window.location.reload()

interface LevelChange {
  status: LevelChangeStatus | null
  /** Смена упала: её ошибка, пока пользователь не закрыл сообщение. */
  failure: string | null
  dismissFailure: () => void
  cancel: () => void
}

/**
 * Состояние смены уровня от backend: читается при открытии, по сигналу (423 на запись,
 * сохранение настроек), при возврате на вкладку и раз в секунду, пока смена идёт.
 * Закончилась успешно или отменена — страница перечитывается целиком; итог смены, которую
 * страница не застала идущей (она прошла между двумя ответами), тоже считается.
 */
export function useLevelChange(reload: () => void = reloadPage): LevelChange {
  const [status, setStatus] = useState<LevelChangeStatus | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const wasRunning = useRef(false)
  /** Последняя смена, о которой страница уже знает; до первого ответа — никакой. */
  const seenChange = useRef<number | null>(null)

  const apply = useCallback((next: LevelChangeStatus) => {
    setStatus(next)
    const known = seenChange.current
    const unseen = known !== null && next.change_id !== known
    if (!next.running && next.outcome !== null && (wasRunning.current || unseen)) {
      if (next.outcome === 'failed') setFailure(next.error ?? 'Level change failed')
      else reload()
    }
    seenChange.current = next.change_id
    wasRunning.current = next.running
  }, [reload])

  const check = useCallback(() => {
    api.getLevelChange().then(apply, () => {})
  }, [apply])

  useEffect(() => {
    check()
    const unsubscribe = onLevelChange(check)
    const onFocus = () => check()
    window.addEventListener('focus', onFocus)
    return () => {
      unsubscribe()
      window.removeEventListener('focus', onFocus)
    }
  }, [check])

  const running = status?.running ?? false
  useEffect(() => {
    if (!running) return
    const timer = setInterval(check, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [running, check])

  const cancel = useCallback(() => {
    api.cancelLevelChange().then(apply, check)
  }, [apply, check])

  return { status, failure, dismissFailure: () => setFailure(null), cancel }
}
