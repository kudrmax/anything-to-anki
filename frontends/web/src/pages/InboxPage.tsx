import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Plus } from 'lucide-react'
import { api } from '@/api/client'
import type { SourceSummary } from '@/api/types'
import { SourceCard } from '@/components/SourceCard'
import { useSourcePolling } from '@/hooks/useSourcePolling'

function StatWidget({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass-card rounded-2xl flex flex-col items-center justify-center py-4 px-2 text-center">
      <div className="text-3xl font-bold grad-text leading-none">{value}</div>
      <div className="text-[11px] font-medium mt-1.5" style={{ color: 'var(--tm)' }}>{label}</div>
    </div>
  )
}

function ProgressCard({
  cefrLevel,
  learnCount,
  candidateCount,
}: {
  cefrLevel: string
  learnCount: number
  candidateCount: number
}) {
  const pct = candidateCount > 0 ? Math.round((learnCount / candidateCount) * 100) : 0
  return (
    <div className="glass-card rounded-2xl px-5 py-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{cefrLevel} progress</span>
        <span className="text-xs" style={{ color: 'var(--tm)' }}>{pct}%</span>
      </div>
      <div className="h-[5px] rounded-full overflow-hidden" style={{ background: 'var(--glass-b)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: 'var(--grad)' }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--tm)' }}>
          {candidateCount} total · {learnCount} to learn
        </span>
        <span className="text-sm font-bold grad-text">{cefrLevel}</span>
      </div>
    </div>
  )
}

export function InboxPage() {
  const navigate = useNavigate()
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [text, setText] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set())
  const processingIdsRef = useRef(processingIds)
  processingIdsRef.current = processingIds
  const [cefrLevel, setCefrLevel] = useState('B2')

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
    void api.getSettings().then((s) => setCefrLevel(s.cefr_level)).catch(() => {})
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

  const handleReview = (id: number) => {
    navigate(`/sources/${id}/review`)
  }

  const handleExport = (id: number) => {
    navigate(`/sources/${id}/export`)
  }

  const isSidebar = import.meta.env.VITE_LAYOUT === 'sidebar'

  return (
    <div className="flex-1 overflow-y-auto">
      <main className={
        isSidebar
          ? 'max-w-2xl mx-auto px-6 py-6 flex flex-col gap-6'
          : 'mx-auto max-w-6xl px-4 py-8 grid grid-cols-1 gap-8 lg:grid-cols-[400px_1fr]'
      }>
        {/* Form */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
            Add source
          </h2>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste text, lyrics, or subtitles here…"
            rows={8}
            className="w-full rounded-lg px-4 py-3 text-sm resize-none transition-colors cosmic-input"
            style={{
              background:   'var(--ibg)',
              border:       '1.5px solid var(--ib)',
              color:        'var(--text)',
            }}
          />
          {error && <p className="text-xs text-rose-400">{error}</p>}
          <button
            onClick={handleAdd}
            disabled={adding || !text.trim()}
            className="flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 transition-all hover:brightness-110 hover:-translate-y-px cursor-pointer"
            style={{ background: 'var(--accent)', boxShadow: '0 4px 14px var(--ag)' }}
          >
            {adding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Add source
          </button>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-2">
            <StatWidget label="To learn" value={sources.reduce((s, r) => s + r.learn_count, 0)} />
            <StatWidget label="Candidates" value={sources.reduce((s, r) => s + r.candidate_count, 0)} />
            <StatWidget label="Sources" value={sources.length} />
          </div>

          {/* Progress */}
          <ProgressCard
            cefrLevel={cefrLevel}
            learnCount={sources.reduce((s, r) => s + r.learn_count, 0)}
            candidateCount={sources.reduce((s, r) => s + r.candidate_count, 0)}
          />
        </section>

        {/* Source list */}
        <section className="flex flex-col gap-4">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
            Sources{sources.length > 0 && <span className="ml-2" style={{ color: 'var(--td)' }}>({sources.length})</span>}
          </h2>

          {sources.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center" style={{ borderColor: 'var(--glass-b)' }}>
              <p className="text-sm" style={{ color: 'var(--td)' }}>No sources yet. Add one to get started.</p>
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
