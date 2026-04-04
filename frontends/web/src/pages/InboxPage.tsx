import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Plus, Settings } from 'lucide-react'
import { api } from '@/api/client'
import type { SourceSummary } from '@/api/types'
import { SourceCard } from '@/components/SourceCard'
import { useSourcePolling } from '@/hooks/useSourcePolling'

export function InboxPage() {
  const navigate = useNavigate()
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [text, setText] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set())
  const processingIdsRef = useRef(processingIds)
  processingIdsRef.current = processingIds

  const loadSources = useCallback(async () => {
    try {
      const list = await api.listSources()
      setSources(list)
    } catch {
      // ignore background reload errors
    }
  }, [])

  useEffect(() => {
    void loadSources()
  }, [loadSources])

  const handleDone = useCallback(
    (updated: SourceSummary) => {
      setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setProcessingIds((prev) => {
        const next = new Set(prev)
        next.delete(updated.id)
        return next
      })
    },
    [],
  )

  const { start: startPolling } = useSourcePolling(null, handleDone)

  const handleAdd = async () => {
    if (!text.trim()) return
    setAdding(true)
    setError(null)
    try {
      const created = await api.createSource(text.trim())
      setText('')
      const newSource: SourceSummary = {
        id: created.id,
        raw_text_preview: text.trim().slice(0, 100),
        status: 'new',
        created_at: new Date().toISOString(),
        candidate_count: 0,
      }
      setSources((prev) => [newSource, ...prev])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add source')
    } finally {
      setAdding(false)
    }
  }

  const handleProcess = async (id: number) => {
    try {
      await api.processSource(id)
      setSources((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'processing' as const } : s)),
      )
      setProcessingIds((prev) => new Set(prev).add(id))
      startPolling(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start processing')
    }
  }

  const handleReview = (id: number) => {
    navigate(`/sources/${id}/review`)
  }

  const handleExport = (id: number) => {
    navigate(`/sources/${id}/export`)
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">VocabMiner</h1>
          <p className="text-xs text-slate-500 mt-0.5">Vocabulary extraction from any text</p>
        </div>
        <button
          onClick={() => navigate('/settings')}
          className="p-2 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
          aria-label="Settings"
        >
          <Settings size={16} />
        </button>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 grid grid-cols-1 gap-8 lg:grid-cols-[400px_1fr]">
        {/* Form */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
            Add source
          </h2>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste text, lyrics, or subtitles here…"
            rows={8}
            className="w-full rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-200 placeholder:text-slate-600 resize-none focus:border-indigo-700 focus:outline-none transition-colors"
          />
          {error && <p className="text-xs text-rose-400">{error}</p>}
          <button
            onClick={handleAdd}
            disabled={adding || !text.trim()}
            className="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
          >
            {adding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Add source
          </button>
        </section>

        {/* Source list */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
            Sources{sources.length > 0 && <span className="ml-2 text-slate-600">({sources.length})</span>}
          </h2>

          {sources.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-800 p-8 text-center">
              <p className="text-sm text-slate-600">No sources yet. Add one to get started.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {sources.map((s) => (
                <SourceCard
                  key={s.id}
                  source={s}
                  onProcess={handleProcess}
                  onReview={handleReview}
                  onExport={handleExport}
                  isProcessingLocal={processingIds.has(s.id)}
                />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
