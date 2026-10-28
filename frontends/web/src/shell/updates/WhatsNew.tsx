import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { ChangelogEntry } from '@/api/types'
import { ChangelogModal } from './ChangelogModal'

/** Первое открытие после обновления: версии, вышедшие с последней увиденной. */
export function WhatsNew() {
  const [entries, setEntries] = useState<ChangelogEntry[]>([])

  useEffect(() => {
    api.getUnseenChangelog().then(setEntries, () => {})
  }, [])

  if (entries.length === 0) return null
  const close = () => {
    setEntries([])
    // Отказ (долгая операция) не страшен: попап покажется при следующем открытии.
    api.markChangelogSeen().catch(() => {})
  }
  return <ChangelogModal mode="whatsnew" entries={entries} onClose={close} />
}
