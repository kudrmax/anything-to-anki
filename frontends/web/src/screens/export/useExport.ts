import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { ExportSection, GlobalExport, Settings, SyncResult } from '@/api/types'
import { useAnkiStatus } from '@/hooks/useAnkiStatus'
import { useToast } from '@/ui'

/** Экспорт одного источника (sourceId задан) или всех сразу. */
export function useExport(sourceId?: number) {
  const ankiStatus = useAnkiStatus()
  const [sections, setSections] = useState<ExportSection[]>([])
  const [exportedCount, setExportedCount] = useState(0)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<SyncResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [toast, showToast] = useToast()

  const applyExport = useCallback((data: GlobalExport) => {
    setSections(data.sections)
    setExportedCount(data.exported_count)
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        applyExport(await api.getExportCards(sourceId))
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    void load()
    api.getSettings().then(setSettings).catch(() => {})
  }, [sourceId, applyExport])

  const sync = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      setResult(await api.syncToAnki(sourceId))
      applyExport(await api.getExportCards(sourceId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }, [sourceId, applyExport])

  const generate = useCallback(async (candidateId: number) => {
    setGeneratingIds(prev => new Set(prev).add(candidateId))
    try {
      const res = await api.generateMeaning(candidateId)
      setSections(prev => prev.map(section => ({
        ...section,
        cards: section.cards.map(c => c.candidate_id === candidateId
          ? { ...c, meaning: res.meaning, translation: res.translation, synonyms: res.synonyms, examples: res.examples, ipa: res.ipa }
          : c),
      })))
      showToast(`Tokens used: ${res.tokens_used}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGeneratingIds(prev => {
        const next = new Set(prev)
        next.delete(candidateId)
        return next
      })
    }
  }, [showToast])

  const cards = sections.flatMap(section => section.cards)
  const totalCards = cards.length

  return {
    ankiStatus, sections, exportedCount, settings, loading, syncing, result, error, generatingIds, toast,
    totalCards, readyCards: cards.filter(card => card.meaning).length,
    canSync: ankiStatus?.available === true && totalCards > 0 && !syncing,
    sync, generate,
  }
}
