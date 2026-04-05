import { useCallback, useEffect, useState } from 'react'
import { CheckCircle, Loader2, Trash2, XCircle } from 'lucide-react'
import { api } from '@/api/client'
import type { CreateNoteTypeResponse, KnownWord, PromptTemplate, Settings, VerifyNoteTypeResponse } from '@/api/types'
import { PROMPT_LABELS } from '@/api/types'

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
  const [_settings, setSettings] = useState<Settings | null>(null)
  const [form, setForm] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [knownWords, setKnownWords] = useState<KnownWord[]>([])
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const [prompts, setPrompts] = useState<PromptTemplate[]>([])
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [promptDraft, setPromptDraft] = useState<{ system_prompt: string; user_template: string } | null>(null)
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [promptError, setPromptError] = useState<string | null>(null)
  const [promptSavedKey, setPromptSavedKey] = useState<string | null>(null)

  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<VerifyNoteTypeResponse | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)

  const [creating, setCreating] = useState(false)
  const [createResult, setCreateResult] = useState<CreateNoteTypeResponse | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [s, words, pts] = await Promise.all([api.getSettings(), api.getKnownWords(), api.getPrompts()])
        setSettings(s)
        setForm(s)
        setKnownWords(words)
        setPrompts(pts)
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

  const setField = (key: keyof Settings, value: string | boolean) => {
    setForm((prev) => prev ? { ...prev, [key]: value } : prev)
    setVerifyResult(null)
    setCreateResult(null)
  }

  const autoResize = (el: HTMLTextAreaElement | null) => {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  const handleEditPrompt = (pt: PromptTemplate) => {
    setEditingKey(pt.function_key)
    setPromptDraft({ system_prompt: pt.system_prompt, user_template: pt.user_template })
    setPromptError(null)
    setPromptSavedKey(null)
  }

  const handleCancelEdit = () => {
    setEditingKey(null)
    setPromptDraft(null)
    setPromptError(null)
  }

  const handleSavePrompt = useCallback(async (functionKey: string) => {
    if (!promptDraft) return
    setSavingPrompt(true)
    setPromptError(null)
    try {
      const updated = await api.updatePrompt(functionKey, promptDraft)
      setPrompts((prev) => prev.map((p) => (p.function_key === functionKey ? updated : p)))
      setPromptSavedKey(functionKey)
      setTimeout(() => {
        setPromptSavedKey(null)
        setEditingKey(null)
        setPromptDraft(null)
      }, 1500)
    } catch (e) {
      setPromptError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSavingPrompt(false)
    }
  }, [promptDraft])

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

          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-col gap-0.5">
              <span className="text-sm" style={{ color: 'var(--text)' }}>Fetch definitions</span>
              <p className="text-xs" style={{ color: 'var(--td)' }}>
                Look up definitions and IPA from dictionary during processing. Disabling speeds up processing.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={form.enable_definitions}
              onClick={() => setField('enable_definitions', !form.enable_definitions)}
              className="relative shrink-0 inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer"
              style={{ background: form.enable_definitions ? 'var(--accent)' : 'var(--glass-b)' }}
            >
              <span
                className="inline-block h-4 w-4 rounded-full bg-white transition-transform"
                style={{ transform: form.enable_definitions ? 'translateX(1.375rem)' : 'translateX(0.25rem)' }}
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

        {/* AI Prompts section */}
        {prompts.length > 0 && (
          <section className="flex flex-col gap-4">
            <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>AI Prompts</h2>
            {prompts.map((pt) => (
              <div key={pt.function_key} className="glass-card rounded-xl p-4 flex flex-col gap-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>{PROMPT_LABELS[pt.function_key]?.name ?? pt.function_key}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--td)' }}>{PROMPT_LABELS[pt.function_key]?.description ?? ''}</p>
                  </div>
                  {editingKey !== pt.function_key && (
                    <button
                      onClick={() => handleEditPrompt(pt)}
                      className="shrink-0 text-xs px-3 py-1.5 rounded-lg transition-all hover:brightness-110 cursor-pointer"
                      style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                    >
                      Edit
                    </button>
                  )}
                </div>

                {editingKey === pt.function_key && promptDraft && (
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs" style={{ color: 'var(--td)' }}>System prompt</label>
                      <textarea
                        ref={autoResize}
                        value={promptDraft.system_prompt}
                        onChange={(e) => {
                          autoResize(e.currentTarget)
                          setPromptDraft((prev) => prev ? { ...prev, system_prompt: e.target.value } : prev)
                        }}
                        className="rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input resize-none overflow-hidden"
                        style={{ ...INPUT_STYLE, minHeight: '4rem' }}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs" style={{ color: 'var(--td)' }}>User template</label>
                      <textarea
                        ref={autoResize}
                        value={promptDraft.user_template}
                        onChange={(e) => {
                          autoResize(e.currentTarget)
                          setPromptDraft((prev) => prev ? { ...prev, user_template: e.target.value } : prev)
                        }}
                        className="rounded-lg px-4 py-2.5 text-sm font-mono transition-colors cosmic-input resize-none overflow-hidden"
                        style={{ ...INPUT_STYLE, minHeight: '6rem' }}
                      />
                      <p className="text-xs" style={{ color: 'var(--td)' }}>
                        Placeholders: <code style={{ color: 'var(--tm)' }}>{'{lemma}'}</code>,{' '}
                        <code style={{ color: 'var(--tm)' }}>{'{pos}'}</code>,{' '}
                        <code style={{ color: 'var(--tm)' }}>{'{context}'}</code>
                      </p>
                    </div>
                    {promptError && <p className="text-xs text-rose-400">{promptError}</p>}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => void handleSavePrompt(pt.function_key)}
                        disabled={savingPrompt}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer text-white"
                        style={{ background: 'var(--accent)' }}
                      >
                        {savingPrompt && <Loader2 size={11} className="animate-spin" />}
                        {promptSavedKey === pt.function_key ? 'Saved ✓' : 'Save'}
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        disabled={savingPrompt}
                        className="text-xs px-3 py-1.5 rounded-lg disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
                        style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </section>
        )}

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

      </main>
    </div>
  )
}
