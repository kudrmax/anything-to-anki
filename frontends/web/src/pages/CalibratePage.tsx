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
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    )
  }

  if (words.length === 0) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-xl font-semibold mb-6">Calibrate Vocabulary</h1>
        <p className="text-neutral-500 mb-6">All words reviewed.</p>
        <button
          onClick={() => navigate('/settings')}
          className="px-4 py-2 rounded-lg bg-neutral-800 text-white hover:bg-neutral-700 transition-colors"
        >
          Finish
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold mb-2">Calibrate Vocabulary</h1>
      <p className="text-sm text-neutral-500 mb-6">
        Tap words you already know. Then press &quot;Next&quot; to continue.
      </p>

      <div className="flex flex-wrap gap-2 mb-8">
        {words.map(w => (
          <button
            key={w.lemma}
            onClick={() => toggleWord(w.lemma)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors border ${
              selected.has(w.lemma)
                ? 'bg-green-600 text-white border-green-600'
                : 'bg-neutral-100 text-neutral-700 border-neutral-300 hover:border-neutral-400 dark:bg-neutral-800 dark:text-neutral-300 dark:border-neutral-600 dark:hover:border-neutral-500'
            }`}
          >
            {w.lemma}
          </button>
        ))}
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => saveAndContinue(false)}
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-neutral-800 text-white hover:bg-neutral-700 disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving...' : `Next ${words.length} words`}
        </button>
        <button
          onClick={() => saveAndContinue(true)}
          disabled={saving}
          className="px-4 py-2 rounded-lg border border-neutral-300 text-neutral-700 hover:bg-neutral-100 disabled:opacity-50 transition-colors dark:border-neutral-600 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          Finish
        </button>
      </div>
    </div>
  )
}
