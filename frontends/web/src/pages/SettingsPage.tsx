import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle, Loader2, RefreshCw, Trash2, XCircle } from 'lucide-react'
import { api } from '@/api/client'
import type { BootstrapStatus, CleanupMediaKind, CreateNoteTypeResponse, KnownWord, Settings, SourceMediaStats, VerifyNoteTypeResponse } from '@/api/types'
import { autoPlayAudioPref } from '@/lib/preferences'
import { useTheme } from '@/lib/ThemeProvider'
import type { ThemeName } from '@/lib/preferences'

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
const AI_MODELS = [
  { value: 'haiku', label: 'Claude Haiku' },
  { value: 'sonnet', label: 'Claude Sonnet' },
  { value: 'opus', label: 'Claude Opus' },
]

const USAGE_GROUP_LABELS: Record<string, string> = {
  neutral: 'Standard, unmarked words',
  informal: 'Slang, casual speech',
  formal: 'Formal register',
  specialized: 'Technical, domain-specific',
  connotation: 'Disapproving, approving, humorous',
  'old-fashioned': 'Dated, archaic',
  offensive: 'Offensive language',
  other: 'Literary, trademark, etc.',
}

const TTS_VOICES: { id: string; label: string; accent: string; gender: string }[] = [
  { id: 'af_heart', label: 'Heart', accent: 'US', gender: 'F' },
  { id: 'af_alloy', label: 'Alloy', accent: 'US', gender: 'F' },
  { id: 'af_aoede', label: 'Aoede', accent: 'US', gender: 'F' },
  { id: 'af_bella', label: 'Bella', accent: 'US', gender: 'F' },
  { id: 'af_jessica', label: 'Jessica', accent: 'US', gender: 'F' },
  { id: 'af_kore', label: 'Kore', accent: 'US', gender: 'F' },
  { id: 'af_nicole', label: 'Nicole', accent: 'US', gender: 'F' },
  { id: 'af_nova', label: 'Nova', accent: 'US', gender: 'F' },
  { id: 'af_river', label: 'River', accent: 'US', gender: 'F' },
  { id: 'af_sarah', label: 'Sarah', accent: 'US', gender: 'F' },
  { id: 'af_sky', label: 'Sky', accent: 'US', gender: 'F' },
  { id: 'am_adam', label: 'Adam', accent: 'US', gender: 'M' },
  { id: 'am_echo', label: 'Echo', accent: 'US', gender: 'M' },
  { id: 'am_eric', label: 'Eric', accent: 'US', gender: 'M' },
  { id: 'am_fenrir', label: 'Fenrir', accent: 'US', gender: 'M' },
  { id: 'am_liam', label: 'Liam', accent: 'US', gender: 'M' },
  { id: 'am_michael', label: 'Michael', accent: 'US', gender: 'M' },
  { id: 'am_onyx', label: 'Onyx', accent: 'US', gender: 'M' },
  { id: 'am_puck', label: 'Puck', accent: 'US', gender: 'M' },
  { id: 'am_santa', label: 'Santa', accent: 'US', gender: 'M' },
  { id: 'bf_alice', label: 'Alice', accent: 'GB', gender: 'F' },
  { id: 'bf_emma', label: 'Emma', accent: 'GB', gender: 'F' },
  { id: 'bf_isabella', label: 'Isabella', accent: 'GB', gender: 'F' },
  { id: 'bf_lily', label: 'Lily', accent: 'GB', gender: 'F' },
  { id: 'bm_daniel', label: 'Daniel', accent: 'GB', gender: 'M' },
  { id: 'bm_fable', label: 'Fable', accent: 'GB', gender: 'M' },
  { id: 'bm_george', label: 'George', accent: 'GB', gender: 'M' },
  { id: 'bm_lewis', label: 'Lewis', accent: 'GB', gender: 'M' },
]

const INPUT_STYLE = {
  background: 'var(--ibg)',
  border: '1.5px solid var(--ib)',
  color: 'var(--text)',
} as const

export function SettingsPage() {
  const navigate = useNavigate()
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null)
  const [_settings, setSettings] = useState<Settings | null>(null)
  const [form, setForm] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [knownWords, setKnownWords] = useState<KnownWord[]>([])
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<VerifyNoteTypeResponse | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)

  const [creating, setCreating] = useState(false)
  const [createResult, setCreateResult] = useState<CreateNoteTypeResponse | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)

  const [mediaStats, setMediaStats] = useState<SourceMediaStats[]>([])
  const [mediaStatsLoading, setMediaStatsLoading] = useState(false)

  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dropTargetIndex, setDropTargetIndex] = useState<number | null>(null)
  const dragCounter = useRef(0)

  const [copiedTemplate, setCopiedTemplate] = useState<'front' | 'back' | 'css' | null>(null)

  const { theme, setTheme } = useTheme()

  const [autoPlayAudio, setAutoPlayAudio] = useState<boolean>(() => autoPlayAudioPref.read())
  const handleAutoPlayToggle = (next: boolean) => {
    setAutoPlayAudio(next)
    autoPlayAudioPref.write(next)
  }

  const loadMediaStats = useCallback(async () => {
    setMediaStatsLoading(true)
    try {
      const stats = await api.getMediaStats()
      setMediaStats(stats)
    } catch {
      /* ignore */
    } finally {
      setMediaStatsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMediaStats()
  }, [loadMediaStats])

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null

    const fetchStatus = async () => {
      try {
        const s = await api.getBootstrapStatus()
        setBootstrapStatus(s)
        if (s.status === 'building' && !timer) {
          timer = setInterval(async () => {
            const updated = await api.getBootstrapStatus()
            setBootstrapStatus(updated)
            if (updated.status !== 'building' && timer) {
              clearInterval(timer)
              timer = null
            }
          }, 2000)
        }
      } catch { /* ignore */ }
    }
    fetchStatus()

    return () => { if (timer) clearInterval(timer) }
  }, [])

  const handleBootstrapBuild = async () => {
    try {
      await api.startBootstrapBuild()
      setBootstrapStatus(prev => prev ? { ...prev, status: 'building' } : prev)
      const timer = setInterval(async () => {
        const updated = await api.getBootstrapStatus()
        setBootstrapStatus(updated)
        if (updated.status !== 'building') clearInterval(timer)
      }, 2000)
    } catch { /* ignore */ }
  }

  const handleCleanup = async (sourceId: number, kind: CleanupMediaKind) => {
    const kindLabel = kind === 'all' ? 'all media' : kind === 'images' ? 'images' : 'audio'
    if (!window.confirm(`Delete ${kindLabel} for this source?`)) return
    try {
      await api.cleanupMedia(sourceId, kind)
      await loadMediaStats()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Cleanup failed')
    }
  }

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    let value = bytes
    let unit = 0
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024
      unit++
    }
    return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`
  }

  useEffect(() => {
    const load = async () => {
      try {
        const [s, words] = await Promise.all([api.getSettings(), api.getKnownWords()])
        setSettings(s)
        setForm(s)
        setKnownWords(words)
      } catch (e) {
        setSaveError(e instanceof Error ? e.message : 'Failed to load settings')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  const handleSave = useCallback(async () => {
    if (!form) return
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      const updated = await api.updateSettings(form)
      setSettings(updated)
      setForm(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }, [form])

  const handleDeleteWord = async (id: number) => {
    setDeletingId(id)
    try {
      await api.deleteKnownWord(id)
      setKnownWords((prev) => prev.filter((w) => w.id !== id))
    } finally {
      setDeletingId(null)
    }
  }

  const handleVerify = useCallback(async () => {
    if (!form) return
    setVerifying(true)
    setVerifyResult(null)
    setVerifyError(null)
    const requiredFields = [
      form.anki_field_sentence,
      form.anki_field_target_word,
      form.anki_field_meaning,
      form.anki_field_ipa,
      form.anki_field_translation,
      form.anki_field_synonyms,
      form.anki_field_examples,
    ].filter(Boolean)
    try {
      const result = await api.verifyNoteType(form.anki_note_type, requiredFields)
      setVerifyResult(result)
    } catch (e) {
      setVerifyError(e instanceof Error ? e.message : 'Anki is not available')
    } finally {
      setVerifying(false)
    }
  }, [form])

  const handleCreate = useCallback(async () => {
    if (!form) return
    setCreating(true)
    setCreateResult(null)
    setCreateError(null)
    const fields = [
      form.anki_field_sentence,
      form.anki_field_target_word,
      form.anki_field_meaning,
      form.anki_field_ipa,
      form.anki_field_translation,
      form.anki_field_synonyms,
      form.anki_field_examples,
      form.anki_field_image,
      form.anki_field_audio,
    ].filter(Boolean)
    try {
      const result = await api.createNoteType(form.anki_note_type, fields)
      setCreateResult(result)
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Anki is not available')
    } finally {
      setCreating(false)
    }
  }, [form])

  const handleCopyTemplate = useCallback(async (part: 'front' | 'back' | 'css') => {
    try {
      const templates = await api.getAnkiTemplates()
      await navigator.clipboard.writeText(templates[part])
      setCopiedTemplate(part)
      setTimeout(() => setCopiedTemplate(null), 2000)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to copy')
    }
  }, [])

  const setField = (key: keyof Settings, value: string | boolean | number | string[]) => {
    setForm((prev) => prev ? { ...prev, [key]: value } : prev)
    setVerifyResult(null)
    setCreateResult(null)
  }

  if (loading || !form) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <main className="mx-auto max-w-lg px-4 py-8 flex flex-col gap-8">

        {/* Appearance section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Appearance</h2>
          <div className="flex gap-3">
            {([
              { name: 'cosmic' as ThemeName, label: 'Cosmic' },
              { name: 'liquid-glass' as ThemeName, label: 'Liquid Glass' },
              { name: 'book' as ThemeName, label: 'Book' },
            ]).map((t) => (
              <button
                key={t.name}
                onClick={() => setTheme(t.name)}
                className="glass-card rounded-xl px-4 py-3 text-sm font-medium cursor-pointer transition-all flex-1"
                style={{
                  color: theme === t.name ? 'var(--accent)' : 'var(--tm)',
                  borderColor: theme === t.name ? 'var(--accent)' : undefined,
                  boxShadow: theme === t.name ? '0 0 0 1px var(--accent)' : undefined,
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </section>

        {/* Anki section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Anki</h2>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="deck-name" className="text-sm" style={{ color: 'var(--text)' }}>Deck name</label>
            <input
              id="deck-name"
              type="text"
              value={form.anki_deck_name}
              onChange={(e) => setField('anki_deck_name', e.target.value)}
              className="rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
              style={INPUT_STYLE}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="note-type" className="text-sm" style={{ color: 'var(--text)' }}>Note type</label>
            <input
              id="note-type"
              type="text"
              value={form.anki_note_type}
              onChange={(e) => setField('anki_note_type', e.target.value)}
              className="rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
              style={INPUT_STYLE}
            />
            <p className="text-xs" style={{ color: 'var(--td)' }}>
              «AnythingToAnkiType» is created automatically. Use your own type for custom fields.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-sm" style={{ color: 'var(--text)' }}>Field mapping</p>
            <div className="glass-card rounded-xl">
              {(
                [
                  { key: 'anki_field_sentence', label: 'Sentence' },
                  { key: 'anki_field_target_word', label: 'Target word' },
                  { key: 'anki_field_meaning', label: 'Meaning' },
                  { key: 'anki_field_ipa', label: 'IPA' },
                  { key: 'anki_field_image', label: 'Image' },
                  { key: 'anki_field_audio', label: 'Audio' },
                  { key: 'anki_field_translation', label: 'Translation' },
                  { key: 'anki_field_synonyms', label: 'Synonyms' },
                  { key: 'anki_field_examples', label: 'Examples' },
                  { key: 'anki_field_audio_target_us', label: 'Audio US' },
                  { key: 'anki_field_audio_target_uk', label: 'Audio UK' },
                  { key: 'anki_field_audio_tts', label: 'Audio TTS' },
                ] as { key: keyof Settings; label: string }[]
              ).map(({ key, label }, i) => (
                <div key={key} className="flex items-center gap-3 px-4 py-2.5" style={i > 0 ? { borderTop: '1px solid var(--glass-b)' } : undefined}>
                  <span className="text-xs w-24 shrink-0" style={{ color: 'var(--td)' }}>{label}</span>
                  <input
                    type="text"
                    value={form[key] as string}
                    onChange={(e) => setField(key, e.target.value)}
                    placeholder="field name"
                    className="flex-1 bg-transparent text-sm focus:outline-none"
                    style={{ color: 'var(--text)' }}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleVerify}
              disabled={verifying || !form.anki_note_type}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
              style={{ border: '1px solid var(--glass-b)', color: 'var(--tm)', background: 'var(--glass)' }}
            >
              {verifying && <Loader2 size={11} className="animate-spin" />}
              Verify note type
            </button>
            <button
              onClick={handleCreate}
              disabled={creating || !form.anki_note_type}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
              style={{ border: '1px solid var(--glass-b)', color: 'var(--accent)', background: 'var(--abg)' }}
            >
              {creating && <Loader2 size={11} className="animate-spin" />}
              Create type
            </button>
            {verifyResult && (
              <span className={`flex items-center gap-1 text-xs ${verifyResult.valid ? 'text-emerald-400' : 'text-rose-400'}`}>
                {verifyResult.valid
                  ? <><CheckCircle size={13} /> Valid</>
                  : <><XCircle size={13} /> Missing: {verifyResult.missing_fields.join(', ')}</>
                }
              </span>
            )}
            {verifyError && <span className="text-xs text-rose-400">{verifyError}</span>}
            {createResult && (
              <span className="flex items-center gap-1 text-xs text-emerald-400">
                <CheckCircle size={13} />
                {createResult.already_existed ? 'Already exists' : 'Created ✓'}
              </span>
            )}
            {createError && <span className="text-xs text-rose-400">{createError}</span>}
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-sm" style={{ color: 'var(--text)' }}>Card template</p>
            <p className="text-xs" style={{ color: 'var(--td)' }}>
              Copy and paste into Anki's card template editor. Field names match your mapping above.
            </p>
            <div className="flex flex-wrap gap-2">
              {(['front', 'back', 'css'] as const).map((part) => (
                <button
                  key={part}
                  onClick={() => void handleCopyTemplate(part)}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:brightness-110 cursor-pointer"
                  style={{ border: '1px solid var(--glass-b)', color: 'var(--tm)', background: 'var(--glass)' }}
                >
                  {copiedTemplate === part
                    ? <><CheckCircle size={11} /> Copied</>
                    : <>{part === 'front' ? 'Copy Front' : part === 'back' ? 'Copy Back' : 'Copy CSS'}</>
                  }
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Vocabulary section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Vocabulary</h2>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="cefr-level" className="text-sm" style={{ color: 'var(--text)' }}>Target CEFR level</label>
            <select
              id="cefr-level"
              value={form.cefr_level}
              onChange={(e) => setField('cefr_level', e.target.value)}
              className="rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
              style={INPUT_STYLE}
            >
              {CEFR_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
            <p className="text-xs" style={{ color: 'var(--td)' }}>
              Words at or above this level will be suggested as candidates.
            </p>
          </div>

        </section>

        {/* Usage Priority section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Usage Priority</h2>
          <p className="text-xs" style={{ color: 'var(--td)' }}>
            Drag to reorder. Words from higher-priority groups appear first among candidates.
          </p>
          <div className="glass-card rounded-xl overflow-hidden">
            {(form.usage_group_order ?? Object.keys(USAGE_GROUP_LABELS)).map((group, idx) => (
              <div
                key={group}
                draggable
                onDragStart={(e) => {
                  setDragIndex(idx)
                  dragCounter.current = 0
                  e.dataTransfer.effectAllowed = 'move'
                  e.dataTransfer.setData('text/plain', String(idx))
                }}
                onDragEnd={() => {
                  setDragIndex(null)
                  setDropTargetIndex(null)
                  dragCounter.current = 0
                }}
                onDragEnter={(e) => {
                  e.preventDefault()
                  dragCounter.current++
                  if (dragIndex !== null && dragIndex !== idx) {
                    setDropTargetIndex(idx)
                  }
                }}
                onDragLeave={() => {
                  dragCounter.current--
                  if (dragCounter.current <= 0) {
                    setDropTargetIndex(null)
                    dragCounter.current = 0
                  }
                }}
                onDragOver={(e) => {
                  e.preventDefault()
                  e.dataTransfer.dropEffect = 'move'
                }}
                onDrop={(e) => {
                  e.preventDefault()
                  dragCounter.current = 0
                  const fromIdx = parseInt(e.dataTransfer.getData('text/plain'), 10)
                  if (isNaN(fromIdx) || fromIdx === idx) {
                    setDropTargetIndex(null)
                    return
                  }
                  const order = [...(form.usage_group_order ?? Object.keys(USAGE_GROUP_LABELS))]
                  const [moved] = order.splice(fromIdx, 1)
                  order.splice(idx, 0, moved)
                  setForm((prev) => prev ? { ...prev, usage_group_order: order } : prev)
                  setDropTargetIndex(null)
                  void api.updateSettings({ usage_group_order: order } as Partial<Settings>)
                }}
                className="flex items-center gap-3 px-4 py-3 select-none"
                style={{
                  borderTop: idx > 0 ? '1px solid var(--glass-b)' : undefined,
                  opacity: dragIndex === idx ? 0.4 : 1,
                  background: dropTargetIndex === idx ? 'var(--glass)' : undefined,
                  cursor: 'grab',
                  transition: 'opacity 150ms, background 150ms',
                }}
              >
                <span className="text-sm shrink-0" style={{ color: 'var(--td)', lineHeight: 1 }}>&#x2817;</span>
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>{group}</span>
                  <span className="text-xs" style={{ color: 'var(--td)' }}>{USAGE_GROUP_LABELS[group] ?? group}</span>
                </div>
                <span className="ml-auto text-xs tabular-nums shrink-0" style={{ color: 'var(--td)' }}>
                  {idx + 1}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Review section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Review</h2>
          <div className="glass-card rounded-xl px-4 py-3 flex items-center justify-between">
            <div className="flex flex-col gap-0.5">
              <span className="text-sm" style={{ color: 'var(--text)' }}>Auto-play audio</span>
              <span className="text-xs" style={{ color: 'var(--td)' }}>
                After marking a word, automatically play the next word's audio (if available).
              </span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={autoPlayAudio}
              onClick={() => handleAutoPlayToggle(!autoPlayAudio)}
              className="relative cursor-pointer transition-colors"
              style={{
                width: '36px',
                height: '20px',
                borderRadius: '999px',
                background: autoPlayAudio ? 'var(--accent)' : 'rgba(148,163,184,0.3)',
                border: '1px solid rgba(255,255,255,0.1)',
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: '1px',
                  left: autoPlayAudio ? '17px' : '1px',
                  width: '16px',
                  height: '16px',
                  borderRadius: '999px',
                  background: '#fff',
                  transition: 'left 120ms ease',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.3)',
                }}
              />
            </button>
          </div>
        </section>

        {/* AI Model section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>AI Model</h2>
          <div className="glass-card rounded-xl px-4 py-3 flex items-center justify-between">
            <span className="text-sm" style={{ color: 'var(--tm)' }}>Provider</span>
            <span className="text-sm" style={{ color: 'var(--text)' }}>Claude</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ai-model" className="text-sm" style={{ color: 'var(--text)' }}>Model</label>
            <select
              id="ai-model"
              value={form.ai_model}
              onChange={(e) => setField('ai_model', e.target.value)}
              className="rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
              style={INPUT_STYLE}
            >
              {AI_MODELS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <p className="text-xs" style={{ color: 'var(--td)' }}>Reserved for future AI-powered features.</p>
          </div>
        </section>

        {/* Text-to-Speech */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Text-to-Speech</h2>

          {/* Speed */}
          <div className="glass-card rounded-xl px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm" style={{ color: 'var(--text)' }}>Speed</span>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  value={form.tts_speed ?? 1.0}
                  onChange={(e) => setField('tts_speed', parseFloat(e.target.value))}
                  className="w-24"
                />
                <span className="text-xs w-8 text-right" style={{ color: 'var(--td)' }}>
                  {(form.tts_speed ?? 1.0).toFixed(1)}
                </span>
              </div>
            </div>
          </div>

          {/* Voices */}
          <p className="text-xs" style={{ color: 'var(--td)' }}>
            Enabled voices (random selection from checked)
          </p>
          <div className="glass-card rounded-xl overflow-hidden" style={{ maxHeight: '300px', overflowY: 'auto' }}>
            {TTS_VOICES.map((voice, i) => {
              const enabled = form.tts_enabled_voices ?? TTS_VOICES.map(v => v.id)
              const isChecked = enabled.includes(voice.id)
              return (
                <label
                  key={voice.id}
                  className="flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-black/5"
                  style={i > 0 ? { borderTop: '1px solid var(--glass-b)' } : undefined}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {
                      const next = isChecked
                        ? enabled.filter((v: string) => v !== voice.id)
                        : [...enabled, voice.id]
                      setField('tts_enabled_voices', next)
                    }}
                  />
                  <span className="text-sm" style={{ color: 'var(--text)' }}>{voice.label}</span>
                  <span className="text-xs ml-auto" style={{ color: 'var(--td)' }}>
                    {voice.accent} {voice.gender}
                  </span>
                </label>
              )
            })}
          </div>
        </section>

        {/* Save button */}
        {saveError && <p className="text-xs text-rose-400">{saveError}</p>}
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 transition-all hover:brightness-110 hover:-translate-y-px cursor-pointer"
          style={{ background: 'var(--accent)', boxShadow: '0 4px 14px var(--ag)' }}
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          {saved ? 'Saved ✓' : 'Save settings'}
        </button>

        {/* Vocabulary Calibration */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Vocabulary Calibration</h2>
          {bootstrapStatus && (
            <div className="space-y-2">
              {bootstrapStatus.status === 'none' && (
                <>
                  <p className="text-sm" style={{ color: 'var(--td)' }}>Calibration data not prepared.</p>
                  <button onClick={handleBootstrapBuild} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:brightness-110 cursor-pointer" style={{ border: '1px solid var(--glass-b)', color: 'var(--accent)', background: 'var(--abg)' }}>
                    Prepare
                  </button>
                </>
              )}
              {bootstrapStatus.status === 'building' && (
                <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--td)' }}>
                  <Loader2 size={14} className="animate-spin" />
                  Preparing calibration data...
                </div>
              )}
              {bootstrapStatus.status === 'error' && (
                <>
                  <p className="text-sm" style={{ color: 'var(--error, #f87171)' }}>{bootstrapStatus.error}</p>
                  <button onClick={handleBootstrapBuild} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:brightness-110 cursor-pointer" style={{ border: '1px solid var(--glass-b)', color: 'var(--accent)', background: 'var(--abg)' }}>
                    Retry
                  </button>
                </>
              )}
              {bootstrapStatus.status === 'ready' && (
                <>
                  <p className="text-sm" style={{ color: 'var(--td)' }}>
                    Ready — {bootstrapStatus.word_count} words
                    {bootstrapStatus.built_at && `, built ${new Date(bootstrapStatus.built_at).toLocaleDateString()}`}
                  </p>
                  <div className="flex gap-2">
                    <button onClick={() => navigate('/calibrate')} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:brightness-110 cursor-pointer" style={{ border: '1px solid var(--glass-b)', color: 'var(--accent)', background: 'var(--abg)' }}>
                      Calibrate vocabulary
                    </button>
                    <button onClick={handleBootstrapBuild} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:brightness-110 cursor-pointer" style={{ border: '1px solid var(--glass-b)', color: 'var(--tm)', background: 'var(--glass)' }}>
                      Rebuild
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </section>

        {/* Whitelist section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
            Whitelist
            {knownWords.length > 0 && (
              <span className="ml-2" style={{ color: 'var(--td)' }}>({knownWords.length})</span>
            )}
          </h2>

          {knownWords.length === 0 ? (
            <p className="text-sm italic" style={{ color: 'var(--td)' }}>No known words yet.</p>
          ) : (
            <div className="glass-card rounded-xl max-h-64 overflow-y-auto">
              {knownWords.map((w, i) => (
                <div key={w.id} className="flex items-center justify-between px-4 py-2.5 gap-2" style={i > 0 ? { borderTop: '1px solid var(--glass-b)' } : undefined}>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm truncate" style={{ color: 'var(--text)' }}>{w.lemma}</span>
                    <span
                      className="shrink-0 text-xs px-1.5 py-0.5 rounded"
                      style={{ color: 'var(--td)', background: 'var(--glass)' }}
                    >
                      {w.pos ? w.pos.toLowerCase() : 'any'}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDeleteWord(w.id)}
                    disabled={deletingId === w.id}
                    className="shrink-0 disabled:opacity-40 transition-colors cursor-pointer hover:text-rose-400"
                    style={{ color: 'var(--td)' }}
                    aria-label={`Remove ${w.lemma}`}
                  >
                    {deletingId === w.id
                      ? <Loader2 size={13} className="animate-spin" />
                      : <Trash2 size={13} />
                    }
                  </button>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs" style={{ color: 'var(--td)' }}>
            Known words won't be suggested when processing new sources.
          </p>
        </section>

        {/* Media storage section */}
        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
              Media storage
            </h2>
            <button
              onClick={() => void loadMediaStats()}
              disabled={mediaStatsLoading}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg cursor-pointer disabled:opacity-50"
              style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
            >
              <RefreshCw size={11} className={mediaStatsLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {mediaStats.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--td)' }}>
              No video sources with media yet.
            </p>
          ) : (
            <div className="glass-card rounded-xl overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ background: 'var(--glass)', color: 'var(--td)' }}>
                    <th className="text-left px-3 py-2 font-medium">Source</th>
                    <th className="text-right px-3 py-2 font-medium">Images</th>
                    <th className="text-right px-3 py-2 font-medium">Audio</th>
                    <th className="text-right px-3 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {mediaStats.map((s) => (
                    <tr key={s.source_id} style={{ borderTop: '1px solid var(--glass-b)', color: 'var(--text)' }}>
                      <td className="px-3 py-2 truncate max-w-[200px]" title={s.source_title}>{s.source_title}</td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--tm)' }}>
                        {formatBytes(s.screenshot_bytes)}
                        {s.screenshot_count > 0 && <span style={{ color: 'var(--td)', marginLeft: '4px' }}>({s.screenshot_count})</span>}
                      </td>
                      <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--tm)' }}>
                        {formatBytes(s.audio_bytes)}
                        {s.audio_count > 0 && <span style={{ color: 'var(--td)', marginLeft: '4px' }}>({s.audio_count})</span>}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => void handleCleanup(s.source_id, 'images')}
                            disabled={s.screenshot_count === 0}
                            title="Delete images only"
                            className="text-xs px-2 py-1 rounded cursor-pointer disabled:opacity-30"
                            style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                          >
                            Del images
                          </button>
                          <button
                            onClick={() => void handleCleanup(s.source_id, 'audio')}
                            disabled={s.audio_count === 0}
                            title="Delete audio only"
                            className="text-xs px-2 py-1 rounded cursor-pointer disabled:opacity-30"
                            style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                          >
                            Del audio
                          </button>
                          <button
                            onClick={() => void handleCleanup(s.source_id, 'all')}
                            disabled={s.screenshot_count === 0 && s.audio_count === 0}
                            title="Delete all media"
                            className="text-xs px-2 py-1 rounded cursor-pointer disabled:opacity-30"
                            style={{ background: 'rgba(244,63,94,.1)', border: '1px solid rgba(244,63,94,.3)', color: 'rgba(244,63,94,.9)' }}
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  <tr style={{ borderTop: '2px solid var(--glass-b)', background: 'var(--glass)', fontWeight: 600, color: 'var(--text)' }}>
                    <td className="px-3 py-2">Total</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {formatBytes(mediaStats.reduce((acc, s) => acc + s.screenshot_bytes, 0))}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {formatBytes(mediaStats.reduce((acc, s) => acc + s.audio_bytes, 0))}
                    </td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </section>

      </main>
    </div>
  )
}
