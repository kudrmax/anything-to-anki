import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { BootstrapStatus, NoteTypeCheck, NoteTypeKind, CleanupMediaKind, FrequentWordThresholdOption, KnownWord, Settings, SourceMediaStats } from '@/api/types'

const BOOTSTRAP_POLL_MS = 2000
const FLASH_MS = 2000

export type TemplatePart = 'front' | 'back' | 'cloze_front' | 'cloze_back' | 'css'

export function useSettings() {
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null)
  const [form, setForm] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [knownWords, setKnownWords] = useState<KnownWord[]>([])
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [noteTypes, setNoteTypes] = useState<NoteTypeCheck[] | null>(null)
  const [noteTypesError, setNoteTypesError] = useState<string | null>(null)
  const [fixingNoteType, setFixingNoteType] = useState<NoteTypeKind | null>(null)
  const [mediaStats, setMediaStats] = useState<SourceMediaStats[]>([])
  const [mediaStatsLoading, setMediaStatsLoading] = useState(false)
  const [copiedTemplate, setCopiedTemplate] = useState<TemplatePart | null>(null)
  const [frequentWordThresholds, setFrequentWordThresholds] = useState<FrequentWordThresholdOption[]>([])

  const loadMediaStats = useCallback(async () => {
    setMediaStatsLoading(true)
    try {
      setMediaStats(await api.getMediaStats())
    } catch {
      /* ignore */
    } finally {
      setMediaStatsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMediaStats()
  }, [loadMediaStats])

  // Статус словаря калибровки: опрашиваем, пока он собирается.
  const isBuilding = bootstrapStatus?.status === 'building'
  useEffect(() => {
    api.getBootstrapStatus().then(setBootstrapStatus).catch(() => {})
  }, [])
  useEffect(() => {
    if (!isBuilding) return
    const timer = setInterval(() => {
      api.getBootstrapStatus().then(setBootstrapStatus).catch(() => {})
    }, BOOTSTRAP_POLL_MS)
    return () => clearInterval(timer)
  }, [isBuilding])

  const buildBootstrap = async () => {
    try {
      await api.startBootstrapBuild()
      setBootstrapStatus(prev => (prev ? { ...prev, status: 'building' } : prev))
    } catch {
      /* ignore */
    }
  }

  const cleanupMedia = async (sourceId: number, kind: CleanupMediaKind) => {
    const kindLabel = kind === 'all' ? 'all media' : kind === 'images' ? 'images' : 'audio'
    if (!window.confirm(`Delete ${kindLabel} for this source?`)) return
    try {
      await api.cleanupMedia(sourceId, kind)
      await loadMediaStats()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Cleanup failed')
    }
  }

  useEffect(() => {
    const load = async () => {
      try {
        const [settings, words, thresholds] = await Promise.all([
          api.getSettings(), api.getKnownWords(), api.getFrequentWordThresholds(),
        ])
        setForm(settings)
        setKnownWords(words)
        setFrequentWordThresholds(thresholds)
      } catch (e) {
        setSaveError(e instanceof Error ? e.message : 'Failed to load settings')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  /** Note type в Anki проверяются по сохранённым настройкам: при открытии и после каждого Save. */
  const loadNoteTypes = useCallback(async () => {
    setNoteTypesError(null)
    try {
      setNoteTypes(await api.getNoteTypes())
    } catch (e) {
      setNoteTypes(null)
      setNoteTypesError(e instanceof Error ? e.message : 'Anki is not available')
    }
  }, [])

  useEffect(() => {
    void loadNoteTypes()
  }, [loadNoteTypes])

  const save = useCallback(async () => {
    if (!form) return
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      setForm(await api.updateSettings(form))
      void loadNoteTypes()
      setSaved(true)
      setTimeout(() => setSaved(false), FLASH_MS)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }, [form, loadNoteTypes])

  const deleteWord = async (id: number) => {
    setDeletingId(id)
    try {
      await api.deleteKnownWord(id)
      setKnownWords(prev => prev.filter(w => w.id !== id))
    } finally {
      setDeletingId(null)
    }
  }

  const fixNoteType = async (kind: NoteTypeKind) => {
    setFixingNoteType(kind)
    setNoteTypesError(null)
    try {
      const fixed = await api.fixNoteType(kind)
      setNoteTypes(prev => prev?.map(t => (t.kind === kind ? fixed : t)) ?? [fixed])
    } catch (e) {
      setNoteTypesError(e instanceof Error ? e.message : 'Anki is not available')
    } finally {
      setFixingNoteType(null)
    }
  }

  const copyTemplate = useCallback(async (part: TemplatePart) => {
    try {
      const templates = await api.getAnkiTemplates()
      await navigator.clipboard.writeText(templates[part])
      setCopiedTemplate(part)
      setTimeout(() => setCopiedTemplate(null), FLASH_MS)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to copy')
    }
  }, [])

  const setField = (key: keyof Settings, value: string | number | string[]) => {
    setForm(prev => (prev ? { ...prev, [key]: value } : prev))
  }

  /** Порядок групп сохраняется сразу, без кнопки Save. */
  const reorderUsageGroups = (order: string[]) => {
    setForm(prev => (prev ? { ...prev, usage_group_order: order } : prev))
    void api.updateSettings({ usage_group_order: order } as Partial<Settings>)
  }

  return {
    form, loading, saving, saved, saveError, setField, save,
    knownWords, deletingId, deleteWord,
    noteTypes, noteTypesError, fixingNoteType, fixNoteType,
    copiedTemplate, copyTemplate,
    bootstrapStatus, buildBootstrap,
    mediaStats, mediaStatsLoading, loadMediaStats, cleanupMedia,
    reorderUsageGroups,
    frequentWordThresholds,
  }
}

export type SettingsStore = ReturnType<typeof useSettings>
