import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, X } from 'lucide-react'
import type { UpdateStep } from '@/api/types'
import { Button, Icon, Kbd, Spinner, Text } from '@/ui'
import { useUpdates } from './useUpdates'
import css from './UpdatingOverlay.module.css'

const STUCK_AFTER_MINUTES = 10
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
              {run.steps.length === 0 && <Spinner />}
              Updating…
            </div>
            {run.steps.length > 0 && <UpdateSteps steps={run.steps} />}
            {status && (
              <div className={css.fallback}>
                <Text tone="soft" size="s">
                  Nothing has changed for {STUCK_AFTER_MINUTES} minutes? Restart the app by hand:
                </Text>
                <ByHand command={status.restart_command} waitFor="Wait until Terminal shows the line that starts with →." />
              </div>
            )}
          </div>
        )
        : <UpdateFailed logTail={run.logTail} command={status?.update_command ?? null} onClose={dismissFailure} />}
    </div>,
    document.body,
  )
}

function UpdateSteps({ steps }: { steps: UpdateStep[] }) {
  return (
    <ol className={css.steps} aria-label="Update steps">
      {steps.map((step, index) => (
        <li key={index} className={css.step} data-status={step.status}>
          <span className={css.mark}><StepMark status={step.status} /></span>
          <Text tone={STEP_TONES[step.status]}>{step.title}</Text>
        </li>
      ))}
    </ol>
  )
}

const STEP_TONES = { done: 'muted', current: 'default', pending: 'muted', failed: 'err' } as const

function StepMark({ status }: { status: UpdateStep['status'] }) {
  if (status === 'current') return <Spinner />
  if (status === 'done') return <Text tone="muted"><Icon as={Check} size="s" /></Text>
  if (status === 'failed') return <Text tone="err"><Icon as={X} size="s" /></Text>
  return null
}

interface UpdateFailedProps {
  logTail: string
  command: string | null
  onClose: () => void
}

function UpdateFailed({ logTail, command, onClose }: UpdateFailedProps) {
  const log = useRef<HTMLPreElement>(null)
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight
  }, [logTail])
  return (
    <div className={css.card} role="alertdialog" aria-modal="true" aria-label="Update failed">
      <h2 className={css.title}>Update failed</h2>
      {logTail && <pre ref={log} className={css.log}>{logTail}</pre>}
      {command && (
        <div className={css.fallback}>
          <Text tone="soft" size="s">Run the update by hand to see what went wrong:</Text>
          <ByHand command={command} waitFor="Wait until Terminal says “Updated to …” or shows an error." />
        </div>
      )}
      <div className={css.footer}>
        <Button onClick={onClose}>Close</Button>
      </div>
    </div>
  )
}

/** Для тех, кто ни разу не открывал терминал: где он, куда вставить команду и чего ждать. */
function ByHand({ command, waitFor }: { command: string; waitFor: string }) {
  return (
    <ol className={css.byHand}>
      <li>
        <Text size="s">
          Open the Terminal app: press <Kbd>⌘</Kbd> <Kbd>Space</Kbd>, type <b>Terminal</b> and press <Kbd>Return</Kbd>.
        </Text>
      </li>
      <li>
        <div className={css.byHandStep}>
          <Text size="s">
            Click <b>Copy</b>, click in the Terminal window, press <Kbd>⌘</Kbd> <Kbd>V</Kbd>, then <Kbd>Return</Kbd>.
          </Text>
          <CommandLine command={command} />
        </div>
      </li>
      <li><Text size="s">{waitFor} Then reload this page.</Text></li>
    </ol>
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
