import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Button, Spinner, Text } from '@/ui'
import { useUpdates } from './useUpdates'
import css from './UpdatingOverlay.module.css'

const UPDATE_COMMAND = 'make update'
const START_COMMAND = 'make up'
const UPDATE_LOG = '.logs/update.log'
const COPY_LABELS = { idle: 'Copy', copied: 'Copied', failed: 'Copy failed' } as const

/** Пока идёт обновление, приложение под ним закрыто; упавшее — объясняет, что делать руками. */
export function UpdatingOverlay() {
  const { run, status, dismissFailure } = useUpdates()
  const running = run?.phase === 'running'

  useEffect(() => {
    if (!running) return
    const swallow = (e: KeyboardEvent) => { e.stopPropagation(); e.preventDefault() }
    window.addEventListener('keydown', swallow, true)
    return () => window.removeEventListener('keydown', swallow, true)
  }, [running])

  if (!run) return null
  return createPortal(
    <div className={css.overlay}>
      {run.phase === 'running'
        ? (
          <div className={`${css.card} ${css.running}`} role="alertdialog" aria-modal="true" aria-label="Updating">
            <div className={css.progress}>
              <Spinner />
              Updating…
            </div>
            <div className={css.fallback}>
              <Text tone="muted" size="s">
                If the app doesn't come back, run this in the app folder. The log is in <code className={css.path}>{UPDATE_LOG}</code>.
              </Text>
              <CommandLine command={START_COMMAND} />
            </div>
          </div>
        )
        : <UpdateFailed logTail={run.logTail} version={status?.current ?? null} onClose={dismissFailure} />}
    </div>,
    document.body,
  )
}

interface UpdateFailedProps {
  logTail: string
  version: string | null
  onClose: () => void
}

function UpdateFailed({ logTail, version, onClose }: UpdateFailedProps) {
  const log = useRef<HTMLPreElement>(null)
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight
  }, [logTail])
  return (
    <div className={css.card} role="alertdialog" aria-modal="true" aria-label="Update failed">
      <h2 className={css.title}>Update failed</h2>
      <Text tone="soft">
        {version ? `The app is still on version ${version}.` : 'The app is still on the previous version.'}
        {' '}Run the update in a terminal from the app folder to see what went wrong.
      </Text>
      {logTail && <pre ref={log} className={css.log}>{logTail}</pre>}
      <CommandLine command={UPDATE_COMMAND} />
      <div className={css.footer}>
        <Button onClick={onClose}>Close</Button>
      </div>
    </div>
  )
}

function CommandLine({ command }: { command: string }) {
  const [copy, setCopy] = useState<'idle' | 'copied' | 'failed'>('idle')
  const copyCommand = () => {
    navigator.clipboard.writeText(command).then(() => setCopy('copied'), () => setCopy('failed'))
  }
  return (
    <div className={css.command}>
      <code>{command}</code>
      <Button onClick={copyCommand}>{COPY_LABELS[copy]}</Button>
    </div>
  )
}
