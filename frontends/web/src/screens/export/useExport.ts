import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { ExportGroup, ExportSection, GlobalExport, Scope, Settings, SyncResult } from '@/api/types'
import { useAnkiStatus } from '@/hooks/useAnkiStatus'
import { statsStore } from '@/hooks/useStats'

const countCards = (sections: ExportSection[]): number =>
  sections.reduce((sum, section) => sum + section.cards.length, 0)

/** Экспорт одного источника (sourceId задан) или области: все, коллекция, неразобранное. */
export function useExport(sourceId?: number, scope: Scope = 'all') {
  const ankiStatus = useAnkiStatus()
  const [groups, setGroups] = useState<Record<ExportGroup, ExportSection[]>>({ ready: [], incomplete: [] })
  const [title, setTitle] = useState<string | null>(null)
  const [exportedCount, setExportedCount] = useState(0)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<ExportGroup | null>(null)
  const [result, setResult] = useState<SyncResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const applyExport = useCallback((data: GlobalExport) => {
    setGroups({ ready: data.ready, incomplete: data.incomplete })
    setExportedCount(data.exported_count)
    setTitle(data.title)
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        applyExport(await api.getExportCards(sourceId, scope))
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    void load()
    api.getSettings().then(setSettings).catch(() => {})
  }, [sourceId, scope, applyExport])

  const sync = useCallback(async (group: ExportGroup) => {
    setSyncing(group)
    setError(null)
    try {
      setResult(await api.syncToAnki(group, sourceId, scope))
      applyExport(await api.getExportCards(sourceId, scope))
      void statsStore.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sync failed')
    } finally {
      setSyncing(null)
    }
  }, [sourceId, scope, applyExport])

  const counts: Record<ExportGroup, number> = { ready: countCards(groups.ready), incomplete: countCards(groups.incomplete) }
  const canSync = (group: ExportGroup) => ankiStatus?.available === true && counts[group] > 0 && syncing === null

  return {
    ankiStatus, groups, counts, totalCards: counts.ready + counts.incomplete,
    title, exportedCount, settings, loading, syncing, result, error,
    canSync, sync,
  }
}
