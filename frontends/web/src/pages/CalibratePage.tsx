import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { api } from '@/api/client'
import type { BootstrapWord } from '@/api/types'

const BTN = 'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer'
const BTN_PRIMARY = { border: '1px solid var(--glass-b)', color: 'var(--accent)', background: 'var(--abg)' } as const
const BTN_SECONDARY = { border: '1px solid var(--glass-b)', color: 'var(--tm)', background: 'var(--glass)' } as const

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
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  if (words.length === 0) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-sm font-medium uppercase tracking-wider mb-6" style={{ color: 'var(--tm)' }}>Calibrate Vocabulary</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--td)' }}>All words reviewed.</p>
        <button onClick={() => navigate('/settings')} className={BTN} style={BTN_SECONDARY}>
          Finish
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-sm font-medium uppercase tracking-wider mb-2" style={{ color: 'var(--tm)' }}>Calibrate Vocabulary</h1>
      <p className="text-xs mb-6" style={{ color: 'var(--td)' }}>
        Tap words you already know. Then press &quot;Next&quot; to continue.
      </p>

      <div className="flex flex-wrap gap-2 mb-8">
        {words.map(w => (
          <button
            key={w.lemma}
            onClick={() => toggleWord(w.lemma)}
            className="rounded-full px-3 py-1.5 text-sm font-medium transition-all cursor-pointer hover:brightness-110"
            style={
              selected.has(w.lemma)
                ? { border: '1px solid var(--accent)', color: '#fff', background: 'var(--accent)' }
                : { border: '1px solid var(--glass-b)', color: 'var(--text)', background: 'var(--glass)' }
            }
          >
            {w.lemma}
          </button>
        ))}
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => saveAndContinue(false)}
          disabled={saving}
          className={BTN}
          style={BTN_PRIMARY}
        >
          {saving && <Loader2 size={11} className="animate-spin" />}
          {saving ? 'Saving...' : `Next ${words.length} words`}
        </button>
        <button
          onClick={() => saveAndContinue(true)}
          disabled={saving}
          className={BTN}
          style={BTN_SECONDARY}
        >
          Finish
        </button>
      </div>
    </div>
  )
}
