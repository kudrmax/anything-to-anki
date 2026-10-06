import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { BootstrapStatus, CleanupMediaKind, CreateNoteTypesResponse, FrequentWordThresholdOption, KnownWord, Settings, SourceMediaStats, VerifyNoteTypesResponse } from '@/api/types'

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
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<VerifyNoteTypesResponse | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [createResult, setCreateResult] = useState<CreateNoteTypesResponse | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
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

  const save = useCallback(async () => {
    if (!form) return
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      setForm(await api.updateSettings(form))
      setSaved(true)
      setTimeout(() => setSaved(false), FLASH_MS)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }, [form])

  const deleteWord = async (id: number) => {
    setDeletingId(id)
    try {
      await api.deleteKnownWord(id)
      setKnownWords(prev => prev.filter(w => w.id !== id))
    } finally {
      setDeletingId(null)
    }
  }

  /** Проверка и создание идут по сохранённым настройкам, поэтому форма сперва сохраняется. */
  const verify = useCallback(async () => {
    if (!form) return
    setVerifying(true)
    setVerifyResult(null)
    setVerifyError(null)
    try {
      setForm(await api.updateSettings(form))
      setVerifyResult(await api.verifyNoteTypes())
    } catch (e) {
      setVerifyError(e instanceof Error ? e.message : 'Anki is not available')
    } finally {
      setVerifying(false)
    }
  }, [form])

  const createNoteType = useCallback(async () => {
    if (!form) return
    setCreating(true)
    setCreateResult(null)
    setCreateError(null)
    try {
      setForm(await api.updateSettings(form))
      setCreateResult(await api.createNoteTypes())
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Anki is not available')
    } finally {
      setCreating(false)
    }
  }, [form])

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
    setVerifyResult(null)
    setCreateResult(null)
  }

  /** Порядок групп сохраняется сразу, без кнопки Save. */
  const reorderUsageGroups = (order: string[]) => {
    setForm(prev => (prev ? { ...prev, usage_group_order: order } : prev))
    void api.updateSettings({ usage_group_order: order } as Partial<Settings>)
  }

  return {
    form, loading, saving, saved, saveError, setField, save,
    knownWords, deletingId, deleteWord,
    verifying, verifyResult, verifyError, verify,
    creating, createResult, createError, createNoteType,
    copiedTemplate, copyTemplate,
    bootstrapStatus, buildBootstrap,
    mediaStats, mediaStatsLoading, loadMediaStats, cleanupMedia,
    reorderUsageGroups,
    frequentWordThresholds,
  }
}

export type SettingsStore = ReturnType<typeof useSettings>
