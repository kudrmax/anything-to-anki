import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Banner, Button } from '@/ui'
import { useLevelChange } from './useLevelChange'
import css from './LevelChangeOverlay.module.css'

/** Пока меняется уровень, всё приложение под ним закрыто: процент и отмена. */
export function LevelChangeOverlay() {
  const { status, failure, dismissFailure, cancel } = useLevelChange()
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
          Level was not changed — {failure}
        </Banner>
      )}
      {running && status && createPortal(
        <LevelChangeBlocker percent={status.percent} cancellable={status.cancellable} onCancel={cancel} />,
        document.body,
      )}
    </>
  )
}

interface BlockerProps {
  percent: number
  cancellable: boolean
  onCancel: () => void
}

export function LevelChangeBlocker({ percent, cancellable, onCancel }: BlockerProps) {
  return (
    <div className={css.overlay} role="alertdialog" aria-modal="true" aria-label="Changing level">
      <div className={css.percent}>{percent}%</div>
      <Button onClick={onCancel} disabled={!cancellable}>Cancel</Button>
    </div>
  )
}
