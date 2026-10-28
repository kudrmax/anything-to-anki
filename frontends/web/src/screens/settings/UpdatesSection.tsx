import { useState } from 'react'
import { api } from '@/api/client'
import type { ChangelogEntry } from '@/api/types'
import { messageOf } from '@/lib/apiError'
import { ChangelogModal } from '@/shell/updates/ChangelogModal'
import { useUpdates, type Updates as UpdatesState } from '@/shell/updates/useUpdates'
import { Button, DividerRow, Text } from '@/ui'

function checkHint({ status, checkOutcome }: UpdatesState) {
  if (checkOutcome === 'failed') return <Text tone="err">Couldn't check for updates. Try again later.</Text>
  if (status?.available) return `Version ${status.latest} is available`
  if (checkOutcome === 'latest' && status) return `You're on the latest version (${status.current})`
  return undefined
}

export function Updates() {
  const updates = useUpdates()
  const [history, setHistory] = useState<ChangelogEntry[] | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)

  const openHistory = async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      setHistory(await api.getChangelog())
    } catch (error) {
      setHistoryError(messageOf(error))
    } finally {
      setHistoryLoading(false)
    }
  }

  return (
    <>
      <DividerRow
        last
        label={updates.status ? `Version ${updates.status.current}` : 'Version'}
        hint={historyError ? <Text tone="err">{historyError}</Text> : checkHint(updates)}
      >
        <Button busy={historyLoading} onClick={() => void openHistory()}>Changelog</Button>
        <Button busy={updates.checking} onClick={() => void updates.checkNow()}>Check for updates</Button>
      </DividerRow>
      {history && <ChangelogModal mode="history" entries={history} onClose={() => setHistory(null)} />}
    </>
  )
}
