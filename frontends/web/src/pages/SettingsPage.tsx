import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, CheckCircle, Loader2, RefreshCw, Trash2, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import type { CleanupMediaKind, CreateNoteTypeResponse, KnownWord, Settings, SourceMediaStats, VerifyNoteTypeResponse } from '@/api/types'
import { autoPlayAudioPref } from '@/lib/preferences'
import { useTheme } from '@/lib/ThemeProvider'
import type { ThemeName } from '@/lib/preferences'

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
const AI_MODELS = [
  { value: 'haiku', label: 'Claude Haiku' },
  { value: 'sonnet', label: 'Claude Sonnet' },
  { value: 'opus', label: 'Claude Opus' },
]

const INPUT_STYLE = {
  background: 'var(--ibg)',
  border: '1.5px solid var(--ib)',
  color: 'var(--text)',
} as const

export function SettingsPage() {
  const navigate = useNavigate()
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

  const setField = (key: keyof Settings, value: string | boolean) => {
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
      {/* Floating toolbar */}
      <div className="shrink-0 flex items-center gap-1.5 mb-4">
        <button onClick={() => navigate('/')} className="glass-pill cursor-pointer" style={{ padding: '5px 10px', gap: '6px' }}>
          <ArrowLeft size={12} style={{ color: 'var(--tm)' }} />
          <span style={{ fontSize: '11px', color: 'var(--tm)' }}>Back</span>
        </button>
        <div className="glass-pill" style={{ padding: '5px 12px' }}>
          <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--text)' }}>Settings</span>
        </div>
      </div>
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
                      {w.pos.toLowerCase()}
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
