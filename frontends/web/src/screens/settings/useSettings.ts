import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import { notifyLongOperation } from '@/api/longOperationSignal'
import { messageOf } from '@/lib/apiError'
import type { BootstrapStatus, NoteTypeCheck, NoteTypeKind, CleanupMediaKind, FrequentWordThresholdOption, KnownWord, LearningWords, Settings, SourceMediaStats, UnknownWord } from '@/api/types'

const BOOTSTRAP_POLL_MS = 2000

/** Ключ строки списков Known и Unknown: у слова Known по таймеру нет id. */
export const unknownWordKey = (id: number): string => `unknown:${id}`
const FLASH_MS = 2000
const AUTOSAVE_MS = 400
/** После сохранения таких настроек note type в Anki проверяются заново. */
const ANKI_PREFIX = 'anki_'

/** Изменение, которое ждёт подтверждения пользователя. */
export interface SettingChange {
  key: keyof Settings
  value: Settings[keyof Settings]
}

export type TemplatePart = 'front' | 'back' | 'cloze_front' | 'cloze_back' | 'css'

export function useSettings() {
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null)
  const [form, setForm] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [knownWords, setKnownWords] = useState<KnownWord[]>([])
  const [unknownWords, setUnknownWords] = useState<UnknownWord[]>([])
  const [learningWords, setLearningWords] = useState<LearningWords>({ in_anki: [], awaiting_export: [] })
  const [deletingKey, setDeletingKey] = useState<string | null>(null)
  const [knownError, setKnownError] = useState<string | null>(null)
  const [noteTypes, setNoteTypes] = useState<NoteTypeCheck[] | null>(null)
  const [noteTypesError, setNoteTypesError] = useState<string | null>(null)
  const [fixingNoteType, setFixingNoteType] = useState<NoteTypeKind | null>(null)
  const [mediaStats, setMediaStats] = useState<SourceMediaStats[]>([])
  const [mediaStatsLoading, setMediaStatsLoading] = useState(false)
  const [copiedTemplate, setCopiedTemplate] = useState<TemplatePart | null>(null)
  const [analysisKeys, setAnalysisKeys] = useState<(keyof Settings)[]>([])
  const [confirming, setConfirming] = useState<SettingChange | null>(null)
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
      alert(messageOf(e))
    }
  }

  useEffect(() => {
    const load = async () => {
      try {
        const [settings, words, unknown, thresholds, learning, analysis] = await Promise.all([
          api.getSettings(), api.getKnownWords(), api.getUnknownWords(), api.getFrequentWordThresholds(), api.getLearningWords(),
          api.getAnalysisKeys(),
        ])
        setForm(settings)
        setAnalysisKeys(analysis)
        setKnownWords(words)
        setLearningWords(learning)
        setUnknownWords(unknown)
        setFrequentWordThresholds(thresholds)
      } catch (e) {
        setSaveError(messageOf(e))
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
      setNoteTypesError(messageOf(e))
    }
  }, [])

  useEffect(() => {
    void loadNoteTypes()
  }, [loadNoteTypes])

  /** Изменённые, но ещё не отправленные настройки: уходят только они, остальное не перезаписывается. */
  const pending = useRef<Partial<Settings>>({})
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const commit = useCallback(async () => {
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = null
    const changes = pending.current
    if (Object.keys(changes).length === 0) return
    pending.current = {}
    setSaving(true)
    setSaveError(null)
    try {
      const saved = await api.updateSettings(changes)
      setForm({ ...saved, ...pending.current })
      notifyLongOperation()
      if (Object.keys(changes).some(key => key.startsWith(ANKI_PREFIX))) void loadNoteTypes()
      setSavedAt(Date.now())
    } catch (e) {
      pending.current = { ...changes, ...pending.current }
      setSaveError(messageOf(e))
    } finally {
      setSaving(false)
    }
  }, [loadNoteTypes])

  useEffect(() => () => { void commit() }, [commit])

  const edit = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    pending.current = { ...pending.current, [key]: value }
    setForm(prev => (prev ? { ...prev, [key]: value } : prev))
  }

  /** Сохраняется само, чуть погодя: ползунок и быстрые клики уходят одним запросом.
   *  Настройка, от которой зависит анализ, ждёт подтверждения: она заново анализирует все источники. */
  const change = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    if (analysisKeys.includes(key)) {
      setConfirming({ key, value })
      return
    }
    edit(key, value)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => void commit(), AUTOSAVE_MS)
  }

  const confirmChange = () => {
    if (!confirming) return
    edit(confirming.key, confirming.value)
    setConfirming(null)
    void commit()
  }

  const cancelChange = () => setConfirming(null)

  /** Слово удаляется по ключу, который дал backend; списки перечитываются. */
  const deleteWord = async (word: KnownWord) => {
    setDeletingKey(word.removal_key)
    setKnownError(null)
    try {
      await api.deleteKnownWord(word.removal_key)
      const [known, learning] = await Promise.all([api.getKnownWords(), api.getLearningWords()])
      setKnownWords(known)
      setLearningWords(learning)
    } catch (e) {
      setKnownError(messageOf(e))
    } finally {
      setDeletingKey(null)
    }
  }

  const deleteUnknownWord = async (id: number) => {
    setDeletingKey(unknownWordKey(id))
    try {
      await api.deleteUnknownWord(id)
      setUnknownWords(prev => prev.filter(w => w.id !== id))
    } finally {
      setDeletingKey(null)
    }
  }

  const fixNoteType = async (kind: NoteTypeKind) => {
    setFixingNoteType(kind)
    setNoteTypesError(null)
    try {
      const fixed = await api.fixNoteType(kind)
      setNoteTypes(prev => prev?.map(t => (t.kind === kind ? fixed : t)) ?? [fixed])
    } catch (e) {
      setNoteTypesError(messageOf(e))
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
      alert(messageOf(e))
    }
  }, [])

  return {
    form, loading, saving, savedAt, saveError, change, edit, commit, confirming, confirmChange, cancelChange,
    knownWords, knownError, deletingKey, deleteWord, unknownWords, deleteUnknownWord, learningWords,
    noteTypes, noteTypesError, fixingNoteType, fixNoteType,
    copiedTemplate, copyTemplate,
    bootstrapStatus, buildBootstrap,
    mediaStats, mediaStatsLoading, loadMediaStats, cleanupMedia,
    frequentWordThresholds,
  }
}

export type SettingsStore = ReturnType<typeof useSettings>
