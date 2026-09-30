import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { ReprocessStats } from '@/api/types'
import { Banner, Button, Modal, Text } from '@/ui'

interface ReprocessModalProps {
  sourceId: number
  onClose: () => void
  onReprocess: () => void
  onOpenExport: (sourceId: number) => void
}

export function ReprocessModal({ sourceId, onClose, onReprocess, onOpenExport }: ReprocessModalProps) {
  const [stats, setStats] = useState<ReprocessStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.getReprocessStats(sourceId)
      .then(s => { if (!cancelled) setStats(s) })
      .catch((e: Error) => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [sourceId])

  const hasWarning = stats != null && (stats.learn_count > 0 || stats.known_count > 0)

  return (
    <Modal
      title="Reprocess source"
      onClose={onClose}
      footer={
        <>
          <Button variant="link" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onOpenExport(sourceId)}>Open export page</Button>
          <Button variant="fill" disabled={loading || stats?.has_active_jobs || error != null} onClick={onReprocess}>
            Reprocess source
          </Button>
        </>
      }
    >
      {loading && <Text tone="muted">Loading stats…</Text>}
      {error && <Text tone="err">Failed to load stats: {error}</Text>}
      {stats != null && (
        <>
          <Text tone="soft">
            Will be lost: {stats.learn_count} learn words, {stats.known_count} known words, {stats.skip_count} skip words
          </Text>
          {hasWarning && <Banner tone="warn">To preserve Learn words, export them to Anki first.</Banner>}
          {stats.has_active_jobs && (
            <Banner tone="warn">
              Source has active jobs (meaning/media generation). Cancel them on the source page before reprocessing.
            </Banner>
          )}
        </>
      )}
    </Modal>
  )
}
