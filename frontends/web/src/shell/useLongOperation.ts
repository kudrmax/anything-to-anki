import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import { notifyLongOperationFinished, onLongOperation } from '@/api/longOperationSignal'
import type { LongOperationKind, LongOperationStatus } from '@/api/types'

const POLL_INTERVAL_MS = 1_000

const reloadPage = () => window.location.reload()

/** Упавшая операция: какая и почему. */
export interface LongOperationFailure {
  kind: LongOperationKind | null
  error: string
}

interface LongOperation {
  status: LongOperationStatus | null
  /** Операция упала: её вид и ошибка, пока пользователь не закрыл сообщение. */
  failure: LongOperationFailure | null
  dismissFailure: () => void
  cancel: () => void
}

/**
 * Состояние долгой операции от backend: читается при открытии, по сигналу (423 на запись,
 * запуск операции, сохранение настроек), при возврате на вкладку и раз в секунду, пока
 * операция идёт. Смена уровня, закончившись успешно или отменой, перечитывает страницу
 * целиком; операция над источниками — сообщает экранам, что пора перечитать данные. Итог
 * операции, которую страница не застала идущей (она прошла между двумя ответами), тоже
 * считается.
 */
export function useLongOperation(reload: () => void = reloadPage): LongOperation {
  const [status, setStatus] = useState<LongOperationStatus | null>(null)
  const [failure, setFailure] = useState<LongOperationFailure | null>(null)
  const wasRunning = useRef(false)
  /** Последняя операция, о которой страница уже знает; до первого ответа — никакой. */
  const seenChange = useRef<number | null>(null)

  const apply = useCallback((next: LongOperationStatus) => {
    setStatus(next)
    const known = seenChange.current
    const unseen = known !== null && next.operation_id !== known
    if (!next.running && next.outcome !== null && (wasRunning.current || unseen)) {
      if (next.outcome === 'failed') setFailure({ kind: next.kind, error: next.error ?? 'Unknown error' })
      else if (next.kind === 'level_change') reload()
      else notifyLongOperationFinished()
    }
    seenChange.current = next.operation_id
    wasRunning.current = next.running
  }, [reload])

  const check = useCallback(() => {
    api.getLongOperation().then(apply, () => {})
  }, [apply])

  useEffect(() => {
    check()
    const unsubscribe = onLongOperation(check)
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
    api.cancelLongOperation().then(apply, check)
  }, [apply, check])

  return { status, failure, dismissFailure: () => setFailure(null), cancel }
}
