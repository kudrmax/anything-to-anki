import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Plus, RefreshCw } from 'lucide-react'
import { api } from '@/api/client'
import type { SourceSummary, Stats } from '@/api/types'
import { NavBar } from '@/components/NavBar'
import { SourceCard } from '@/components/SourceCard'
import { useSourcePolling } from '@/hooks/useSourcePolling'

export function InboxPage() {
  const navigate = useNavigate()
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [text, setText] = useState('')
  const [adding, setAdding] = useState(false)
  const [processingAll, setProcessingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set())
  const processingIdsRef = useRef(processingIds)
  processingIdsRef.current = processingIds

  const loadSources = useCallback(async () => {
    try {
      const [list, s] = await Promise.all([api.listSources(), api.getStats()])
      setSources(list)
      setStats(s)
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
      void api.getStats().then(setStats).catch(() => undefined)
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
        learn_count: 0,
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

  const handleProcessAll = async () => {
    const pending = sources.filter((s) => s.status === 'new' || s.status === 'error')
    if (pending.length === 0) return
    setProcessingAll(true)
    try {
      for (const source of pending) {
        try {
          await api.processSource(source.id)
          setSources((prev) =>
            prev.map((s) => (s.id === source.id ? { ...s, status: 'processing' as const } : s)),
          )
          setProcessingIds((prev) => new Set(prev).add(source.id))
          startPolling(source.id)
        } catch {
          // skip individual errors, continue with others
        }
      }
    } finally {
      setProcessingAll(false)
    }
  }

  const handleReview = (id: number) => {
    navigate(`/sources/${id}/review`)
  }

  const handleExport = (id: number) => {
    navigate(`/sources/${id}/export`)
  }

  const pendingCount = sources.filter((s) => s.status === 'new' || s.status === 'error').length

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <NavBar />

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
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
                Sources{sources.length > 0 && <span className="ml-2 text-slate-600">({sources.length})</span>}
              </h2>
              {stats && (
                <span className="text-xs text-slate-600">
                  {stats.learn_count > 0 && (
                    <span className="text-indigo-400">{stats.learn_count} to learn</span>
                  )}
                  {stats.learn_count > 0 && stats.known_word_count > 0 && <span> · </span>}
                  {stats.known_word_count > 0 && (
                    <span>{stats.known_word_count} known</span>
                  )}
                </span>
              )}
            </div>
            {pendingCount > 0 && (
              <button
                onClick={handleProcessAll}
                disabled={processingAll}
                className="flex items-center gap-1.5 rounded-md border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-400 hover:text-slate-200 hover:border-slate-600 disabled:opacity-50 transition-colors cursor-pointer"
              >
                {processingAll
                  ? <Loader2 size={11} className="animate-spin" />
                  : <RefreshCw size={11} />
                }
                Process all ({pendingCount})
              </button>
            )}
          </div>

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
