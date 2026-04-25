import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { api } from '@/api/client'
import type { BootstrapWord } from '@/api/types'

export function CalibratePage() {
  const navigate = useNavigate()
  const [words, setWords] = useState<BootstrapWord[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const excludedRef = useRef<Set<string>>(new Set())

  const fetchWords = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getBootstrapWords([...excludedRef.current])
      setWords(data)
      setSelected(new Set())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchWords()
  }, [fetchWords])

  const toggleWord = (lemma: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(lemma)) {
        next.delete(lemma)
      } else {
        next.add(lemma)
      }
      return next
    })
  }

  const saveAndContinue = async (finish: boolean) => {
    setSaving(true)
    try {
      if (selected.size > 0) {
        await api.saveBootstrapKnown([...selected])
      }
      for (const w of words) {
        excludedRef.current.add(w.lemma)
      }
      if (finish) {
        navigate('/settings')
      } else {
        await fetchWords()
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  if (words.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto">
        <main className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">
          <span className="text-sm" style={{ color: 'var(--td)' }}>All words reviewed.</span>
          <button onClick={() => navigate('/settings')} className="glass-pill cursor-pointer" style={{ alignSelf: 'flex-start' }}>
            <span style={{ color: 'var(--tm)' }}>Finish</span>
          </button>
        </main>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <main className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">

        <p className="text-xs" style={{ color: 'var(--td)' }}>
          Tap words you already know. Then press Next to continue.
        </p>

        <div className="glass-panel overflow-hidden">
          <div
            className="grid"
            style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}
          >
            {words.map((w, i) => {
              const isSelected = selected.has(w.lemma)
              const col = i % 3
              const row = Math.floor(i / 3)
              return (
                <button
                  key={w.lemma}
                  onClick={() => toggleWord(w.lemma)}
                  className="cursor-pointer text-sm font-medium text-center"
                  style={{
                    padding: '14px 6px',
                    background: isSelected ? 'var(--accent)' : 'transparent',
                    color: isSelected ? '#fff' : 'var(--text)',
                    borderRight: col < 2 ? '0.5px solid var(--glass-b)' : undefined,
                    borderBottom: row < Math.ceil(words.length / 3) - 1 ? '0.5px solid var(--glass-b)' : undefined,
                    transition: 'background 150ms ease, color 150ms ease',
                  }}
                >
                  {w.lemma}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => saveAndContinue(false)}
            disabled={saving}
            className="glass-pill glass-pill-prominent cursor-pointer disabled:opacity-50"
          >
            {saving && <Loader2 size={11} className="animate-spin" />}
            <span>{saving ? 'Saving...' : `Next ${words.length} words`}</span>
          </button>
          <button
            onClick={() => saveAndContinue(true)}
            disabled={saving}
            className="glass-pill cursor-pointer disabled:opacity-50"
          >
            <span style={{ color: 'var(--tm)' }}>Finish</span>
          </button>
        </div>

      </main>
    </div>
  )
}
