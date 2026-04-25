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
        <main className="mx-auto max-w-lg px-4 py-8 flex flex-col gap-6">
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
      <main className="mx-auto max-w-lg px-4 py-8 flex flex-col gap-6">

        <p className="text-xs" style={{ color: 'var(--td)' }}>
          Tap words you already know. Then press Next to continue.
        </p>

        <div className="flex flex-wrap gap-2">
          {words.map(w => (
            <button
              key={w.lemma}
              onClick={() => toggleWord(w.lemma)}
              className={`glass-pill cursor-pointer ${selected.has(w.lemma) ? 'glass-pill-prominent' : ''}`}
              style={selected.has(w.lemma) ? { background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' } : undefined}
            >
              <span style={selected.has(w.lemma) ? { color: '#fff' } : { color: 'var(--text)' }}>{w.lemma}</span>
            </button>
          ))}
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
