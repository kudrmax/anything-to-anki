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
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <header
        className="px-6 py-4 flex items-center gap-4"
        style={{ borderBottom: '1px solid var(--glass-b)' }}
      >
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm transition-opacity hover:opacity-100 cursor-pointer"
          style={{ color: 'var(--tm)', opacity: 0.8 }}
        >
          <ArrowLeft size={14} />
          Back
        </button>
        <h1 className="text-base font-semibold" style={{ color: 'var(--text)' }}>Settings</h1>
      </header>

      <main className="mx-auto max-w-lg px-4 py-8 flex flex-col gap-8">
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>Anki</h2>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="deck-name" className="text-sm" style={{ color: 'var(--text)' }}>
              Deck name
            </label>
            <input
              id="deck-name"
              type="text"
              value={deckName}
              onChange={(e) => setDeckName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleSave() }}
              className="rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
              style={{
                background:   'var(--ibg)',
                border:       '1.5px solid var(--ib)',
                color:        'var(--text)',
              }}
            />
            <p className="text-xs" style={{ color: 'var(--td)' }}>
              Cards will be added to this deck in Anki. Default: VocabMiner
            </p>
          </div>

          {error && <p className="text-xs text-rose-400">{error}</p>}

          <button
            onClick={handleSave}
            disabled={saving || !deckName.trim()}
            className="flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
            style={{ background: 'var(--accent)' }}
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saved ? 'Saved ✓' : 'Save'}
          </button>
        </section>

        {settings && (
          <section className="flex flex-col gap-4">
            <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
              Vocabulary
            </h2>
            <div className="glass-card rounded-xl px-4 py-3 flex items-center justify-between">
              <span className="text-sm" style={{ color: 'var(--tm)' }}>Target CEFR level</span>
              <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>{settings.cefr_level}</span>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
