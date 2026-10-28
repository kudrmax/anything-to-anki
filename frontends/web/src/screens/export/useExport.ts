import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { ExportFill, ExportGroup, ExportSection, GlobalExport, SetScope, Settings, SyncResult } from '@/api/types'
import { useAnkiStatus } from '@/hooks/useAnkiStatus'
import { statsStore } from '@/hooks/useStats'
import { messageOf } from '@/lib/apiError'

/** Пока карточки генерируются, экспорт перечитывается: готовые переходят в Ready сами. */
const GENERATING_POLL_MS = 2000
const NO_FILL: ExportFill = { fillable: 0, generating: 0, skipped: [] }

const countCards = (sections: ExportSection[]): number =>
  sections.reduce((sum, section) => sum + section.cards.length, 0)

/** Экспорт набора источников: один источник, коллекция, неразобранное или все. */
export function useExport(scope: SetScope) {
  const ankiStatus = useAnkiStatus()
  const [groups, setGroups] = useState<Record<ExportGroup, ExportSection[]>>({ ready: [], incomplete: [] })
  const [title, setTitle] = useState<string | null>(null)
  const [fillState, setFillState] = useState<ExportFill>(NO_FILL)
  const [filling, setFilling] = useState(false)
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
    setFillState(data.fill)
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        applyExport(await api.getExportCards(scope))
      } catch (e) {
        setError(messageOf(e))
      } finally {
        setLoading(false)
      }
    }
    void load()
    api.getSettings().then(setSettings).catch(() => {})
  }, [scope, applyExport])

  const sync = useCallback(async (group: ExportGroup) => {
    setSyncing(group)
    setError(null)
    try {
      const synced = await api.syncToAnki(group, scope)
      setResult(synced)
      applyExport(await api.getExportCards(scope))
      void statsStore.refresh()
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setSyncing(null)
    }
  }, [scope, applyExport])

  const fill = useCallback(async () => {
    setFilling(true)
    setError(null)
    try {
      applyExport(await api.fillMissing(scope))
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setFilling(false)
    }
  }, [scope, applyExport])

  const generating = fillState.generating > 0
  useEffect(() => {
    if (!generating) return
    const timer = setInterval(() => {
      if (document.hidden) return
      api.getExportCards(scope).then(applyExport).catch(() => {})
    }, GENERATING_POLL_MS)
    return () => clearInterval(timer)
  }, [generating, scope, applyExport])

  const counts: Record<ExportGroup, number> = { ready: countCards(groups.ready), incomplete: countCards(groups.incomplete) }
  const canSync = (group: ExportGroup) => ankiStatus?.available === true && counts[group] > 0 && syncing === null

  return {
    ankiStatus, groups, counts, totalCards: counts.ready + counts.incomplete,
    title, exportedCount, settings, loading, syncing, result, error,
    canSync, sync, fillState, filling, fill,
  }
}
