import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import type { LongOperationKind } from '@/api/types'
import { Banner, Button } from '@/ui'
import { useLongOperation } from './useLongOperation'
import css from './LongOperationOverlay.module.css'

/** Что идёт: подпись оверлея для экранного чтеца. */
const RUNNING: Record<LongOperationKind, string> = {
  level_change: 'Changing level',
  process: 'Processing sources',
  update: 'Finding words again',
  recut: 'Processing again',
  refresh: 'Refreshing topics',
}

/** Что не случилось, если операция упала. */
const NOT_DONE: Record<LongOperationKind, string> = {
  level_change: 'Level was not changed',
  process: 'Sources were not processed',
  update: 'Words were not found again',
  recut: 'Sources were not processed again',
  refresh: 'Topics were not refreshed',
}

/** Пока идёт долгая операция, всё приложение под ним закрыто: процент и отмена. */
export function LongOperationOverlay() {
  const { status, failure, dismissFailure, cancel } = useLongOperation()
  const running = status?.running ?? false

  useEffect(() => {
    if (!running) return
    const swallow = (e: KeyboardEvent) => { e.stopPropagation(); e.preventDefault() }
    window.addEventListener('keydown', swallow, true)
    return () => window.removeEventListener('keydown', swallow, true)
  }, [running])

  return (
    <>
      {failure && (
        <Banner tone="err" onDismiss={dismissFailure}>
          {failure.kind ? NOT_DONE[failure.kind] : 'The operation failed'} — {failure.error}
        </Banner>
      )}
      {running && status && createPortal(
        <LongOperationBlocker
          label={status.kind ? RUNNING[status.kind] : 'Working'}
          percent={status.percent} cancellable={status.cancellable} onCancel={cancel}
        />,
        document.body,
      )}
    </>
  )
}

interface BlockerProps {
  label: string
  percent: number
  cancellable: boolean
  onCancel: () => void
}

export function LongOperationBlocker({ label, percent, cancellable, onCancel }: BlockerProps) {
  return (
    <div className={css.overlay} role="alertdialog" aria-modal="true" aria-label={label}>
      <div className={css.percent}>{percent}%</div>
      <Button onClick={onCancel} disabled={!cancellable}>Cancel</Button>
    </div>
  )
}
