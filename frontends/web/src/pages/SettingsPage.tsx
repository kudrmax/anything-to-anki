import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { api } from '@/api/client'
import type { Settings } from '@/api/types'

export function SettingsPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [deckName, setDeckName] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const s = await api.getSettings()
        setSettings(s)
        setDeckName(s.anki_deck_name)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load settings')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  const handleSave = useCallback(async () => {
    if (!deckName.trim()) return
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await api.updateSettings({ anki_deck_name: deckName.trim() })
      setSettings(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }, [deckName])

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-slate-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
        >
          <ArrowLeft size={14} />
          Back
        </button>
        <h1 className="text-base font-semibold text-slate-100">Settings</h1>
      </header>

      <main className="mx-auto max-w-lg px-4 py-8 flex flex-col gap-8">
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Anki</h2>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="deck-name" className="text-sm text-slate-300">
              Deck name
            </label>
            <input
              id="deck-name"
              type="text"
              value={deckName}
              onChange={(e) => setDeckName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleSave() }}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-indigo-700 focus:outline-none transition-colors"
            />
            <p className="text-xs text-slate-600">
              Cards will be added to this deck in Anki. Default: VocabMiner
            </p>
          </div>

          {error && <p className="text-xs text-rose-400">{error}</p>}

          <button
            onClick={handleSave}
            disabled={saving || !deckName.trim()}
            className="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors cursor-pointer"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saved ? 'Saved ✓' : 'Save'}
          </button>
        </section>

        {settings && (
          <section className="flex flex-col gap-4">
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
              Vocabulary
            </h2>
            <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 flex items-center justify-between">
              <span className="text-sm text-slate-400">Target CEFR level</span>
              <span className="text-sm font-medium text-slate-200">{settings.cefr_level}</span>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
