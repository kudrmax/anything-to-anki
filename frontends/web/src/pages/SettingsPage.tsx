import { useCallback, useEffect, useState } from 'react'
import { CheckCircle, Loader2, Trash2, XCircle } from 'lucide-react'
import { api } from '@/api/client'
import { NavBar } from '@/components/NavBar'
import type { CreateNoteTypeResponse, KnownWord, Settings, VerifyNoteTypeResponse } from '@/api/types'

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
const AI_MODELS = [
  { value: 'haiku', label: 'Claude Haiku' },
  { value: 'sonnet', label: 'Claude Sonnet' },
  { value: 'opus', label: 'Claude Opus' },
]

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
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

  const setField = (key: keyof Settings, value: string) => {
    setForm((prev) => prev ? { ...prev, [key]: value } : prev)
    setVerifyResult(null)
    setCreateResult(null)
  }

  if (loading || !form) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-slate-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <NavBar />

      <main className="mx-auto max-w-lg px-4 py-8 flex flex-col gap-8">

        {/* Anki section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Anki</h2>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-slate-300">Deck name</label>
            <input
              type="text"
              value={form.anki_deck_name}
              onChange={(e) => setField('anki_deck_name', e.target.value)}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-indigo-700 focus:outline-none transition-colors"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-slate-300">Note type</label>
            <input
              type="text"
              value={form.anki_note_type}
              onChange={(e) => setField('anki_note_type', e.target.value)}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-indigo-700 focus:outline-none transition-colors"
            />
            <p className="text-xs text-slate-600">
              «AnythingToAnkiType» is created automatically. Use your own type for custom fields.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-sm text-slate-300">Field mapping</p>
            <div className="rounded-lg border border-slate-800 bg-slate-900 divide-y divide-slate-800">
              {(
                [
                  { key: 'anki_field_sentence', label: 'Sentence' },
                  { key: 'anki_field_target_word', label: 'Target word' },
                  { key: 'anki_field_meaning', label: 'Meaning' },
                  { key: 'anki_field_ipa', label: 'IPA' },
                ] as { key: keyof Settings; label: string }[]
              ).map(({ key, label }) => (
                <div key={key} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="text-xs text-slate-500 w-24 shrink-0">{label}</span>
                  <input
                    type="text"
                    value={form[key] as string}
                    onChange={(e) => setField(key, e.target.value)}
                    placeholder="field name"
                    className="flex-1 bg-transparent text-sm text-slate-200 placeholder:text-slate-700 focus:outline-none"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleVerify}
              disabled={verifying || !form.anki_note_type}
              className="flex items-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-slate-200 hover:border-slate-600 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {verifying && <Loader2 size={11} className="animate-spin" />}
              Verify note type
            </button>
            <button
              onClick={handleCreate}
              disabled={creating || !form.anki_note_type}
              className="flex items-center gap-1.5 rounded-md border border-indigo-800 px-3 py-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300 hover:border-indigo-700 disabled:opacity-50 transition-colors cursor-pointer"
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
            {verifyError && (
              <span className="text-xs text-rose-400">{verifyError}</span>
            )}
            {createResult && (
              <span className="flex items-center gap-1 text-xs text-emerald-400">
                <CheckCircle size={13} />
                {createResult.already_existed ? 'Already exists' : 'Created ✓'}
              </span>
            )}
            {createError && (
              <span className="text-xs text-rose-400">{createError}</span>
            )}
          </div>
        </section>

        {/* Vocabulary section */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Vocabulary</h2>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-slate-300">Target CEFR level</label>
            <select
              value={form.cefr_level}
              onChange={(e) => setField('cefr_level', e.target.value)}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 focus:border-indigo-700 focus:outline-none transition-colors"
            >
              {CEFR_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
            <p className="text-xs text-slate-600">
              Words at or above this level will be suggested as candidates.
            </p>
          </div>
        </section>

        {/* AI Model section (scaffold) */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">AI Model</h2>
          <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 flex items-center justify-between">
            <span className="text-sm text-slate-400">Provider</span>
            <span className="text-sm text-slate-200">Claude</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-slate-300">Model</label>
            <select
              value={form.ai_model}
              onChange={(e) => setField('ai_model', e.target.value)}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 focus:border-indigo-700 focus:outline-none transition-colors"
            >
              {AI_MODELS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <p className="text-xs text-slate-600">Reserved for future AI-powered features.</p>
          </div>
        </section>

        {/* Save button */}
        {saveError && <p className="text-xs text-rose-400">{saveError}</p>}
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors cursor-pointer"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          {saved ? 'Saved ✓' : 'Save settings'}
        </button>

        {/* Whitelist section */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
              Whitelist
              {knownWords.length > 0 && <span className="ml-2 text-slate-600">({knownWords.length})</span>}
            </h2>
            </div>

          {knownWords.length === 0 ? (
            <p className="text-sm text-slate-600 italic">No known words yet.</p>
          ) : (
            <div className="rounded-lg border border-slate-800 bg-slate-900 divide-y divide-slate-800 max-h-64 overflow-y-auto">
              {knownWords.map((w) => (
                <div key={w.id} className="flex items-center justify-between px-4 py-2.5 gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm text-slate-200 truncate">{w.lemma}</span>
                    <span className="shrink-0 text-xs text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded">
                      {w.pos.toLowerCase()}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDeleteWord(w.id)}
                    disabled={deletingId === w.id}
                    className="shrink-0 text-slate-600 hover:text-rose-400 disabled:opacity-40 transition-colors cursor-pointer"
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
          <p className="text-xs text-slate-600">
            Known words won't be suggested when processing new sources.
          </p>
        </section>

      </main>
    </div>
  )
}
