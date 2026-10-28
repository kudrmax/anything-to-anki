import type { ReactNode } from 'react'
import { Button, Modal, Spinner, Stack, Text } from '@/ui'
import { CHECK_FAILED_TEXT, CHECKING_TEXT, latestVersionText } from './checkOutcome'
import { ChangelogModal } from './ChangelogModal'
import { UpdatingOverlay } from './UpdatingOverlay'
import { UpdatesContext, useUpdates, useUpdatesController } from './useUpdates'
import { useNativeCheckForUpdates } from './useNativeCheckForUpdates'

interface UpdatesProviderProps {
  children: ReactNode
  reload?: () => void
}

/** Одно состояние обновлений на всё приложение: индикатор, настройки и меню macOS видят одно и то же. */
export function UpdatesProvider({ children, reload }: UpdatesProviderProps) {
  const updates = useUpdatesController(reload)
  return (
    <UpdatesContext.Provider value={updates}>
      {children}
      <UpdateOffer />
      <UpdatingOverlay />
      <NativeCheckForUpdates />
    </UpdatesContext.Provider>
  )
}

function UpdateOffer() {
  const { status, offerOpen, closeOffer, startUpdate, startError } = useUpdates()
  if (!offerOpen || !status) return null
  return (
    <ChangelogModal
      mode="update"
      entries={status.entries}
      onClose={closeOffer}
      note={startError && <Text tone="err">{startError}</Text>}
      action={<Button variant="fill" onClick={() => void startUpdate()}>Update</Button>}
    />
  )
}

function NativeCheckForUpdates() {
  const { status } = useUpdates()
  const { check, dismiss } = useNativeCheckForUpdates()
  if (!check) return null
  return (
    <Modal title="Check for updates" onClose={dismiss} footer={<Button onClick={dismiss}>Close</Button>}>
      {check === 'checking'
        ? <Stack row><Spinner /><Text>{CHECKING_TEXT}</Text></Stack>
        : check === 'failed' || !status
          ? <Text tone="err">{CHECK_FAILED_TEXT}</Text>
          : <Text>{latestVersionText(status.current)}</Text>}
    </Modal>
  )
}
