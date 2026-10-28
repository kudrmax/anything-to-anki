import type { ReactNode } from 'react'
import { Button, Text } from '@/ui'
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
  useNativeCheckForUpdates()
  return null
}
