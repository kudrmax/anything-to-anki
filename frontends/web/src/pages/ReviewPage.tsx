import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { api } from '@/api/client'
import type { CandidateStatus, SourceDetail, StoredCandidate } from '@/api/types'
import { CandidateCard } from '@/components/CandidateCard'
import { TextAnnotator } from '@/components/TextAnnotator'

function sortCandidates(candidates: StoredCandidate[]): StoredCandidate[] {
  const cefrOrder: Record<string, number> = { C2: 4, C1: 3, B2: 2, B1: 1, A2: 0, A1: 0 }
  return [...candidates].sort((a, b) => {
    if (a.is_sweet_spot !== b.is_sweet_spot) return a.is_sweet_spot ? -1 : 1
    return (cefrOrder[b.cefr_level] ?? 0) - (cefrOrder[a.cefr_level] ?? 0)
  })
}

export function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const sourceId = Number(id)

  const [source, setSource] = useState<SourceDetail | null>(null)
  const [candidates, setCandidates] = useState<StoredCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [hoveredId, setHoveredId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const rightPanelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [src, cands] = await Promise.all([
          api.getSource(sourceId),
          api.getCandidates(sourceId),
        ])
        setSource(src)
        setCandidates(sortCandidates(cands))
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [sourceId])

  const handleMark = useCallback(async (candidateId: number, status: CandidateStatus) => {
    await api.markCandidate(candidateId, status)
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, status } : c)),
    )
  }, [])

  const handleWordClick = useCallback((candidateId: number) => {
    const el = rightPanelRef.current?.querySelector(`[data-candidate-id="${candidateId}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    setHoveredId(candidateId)
    setTimeout(() => setHoveredId(null), 1500)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const anyPending = candidates.some((c) => c.status === 'pending')
      const newStatus = anyPending ? 'partially_reviewed' : 'reviewed'
      await api.updateSourceStatus(sourceId, newStatus)
      navigate('/')
    } catch {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-slate-500" />
      </div>
    )
  }

  if (!source) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <p className="text-slate-500">Source not found.</p>
      </div>
    )
  }

  const markedCount = candidates.filter((c) => c.status !== 'pending').length
  const learnCount = candidates.filter((c) => c.status === 'learn').length
  const progress = candidates.length > 0 ? (markedCount / candidates.length) * 100 : 0
  const annotationText = source.cleaned_text ?? source.raw_text

  return (
    <div className="h-screen bg-slate-950 text-slate-100 font-sans flex flex-col overflow-hidden">
      {/* Header */}
      <header className="shrink-0 border-b border-slate-800 px-6 py-3 flex items-center justify-between gap-4">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </button>

        <div className="flex-1 max-w-sm">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Marked: {markedCount} / {candidates.length}</span>
            <span className="text-slate-500">To learn: {learnCount}</span>
          </div>
          <div className="h-1 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-indigo-600 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(`/sources/${sourceId}/export`)}
            className="rounded-lg border border-indigo-700 px-4 py-1.5 text-sm font-medium text-indigo-400 hover:bg-indigo-950 transition-colors cursor-pointer"
          >
            Export →
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors cursor-pointer"
          >
            {saving && <Loader2 size={12} className="animate-spin" />}
            Save and exit
          </button>
        </div>
      </header>

      {/* Split panels */}
      <div className="flex-1 overflow-hidden flex">
        {/* Left: text */}
        <div className="w-[55%] overflow-y-auto border-r border-slate-800 p-6">
          <h2 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-4">
            Source text
          </h2>
          <TextAnnotator
            text={annotationText}
            candidates={candidates}
            hoveredCandidateId={hoveredId}
            onWordClick={handleWordClick}
            onWordHover={setHoveredId}
          />
        </div>

        {/* Right: candidates */}
        <div ref={rightPanelRef} className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          <h2 className="text-xs font-medium text-slate-500 uppercase tracking-wider px-1">
            Candidates {candidates.length > 0 && `(${candidates.length})`}
          </h2>
          {candidates.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-800 p-6 text-center">
              <p className="text-sm text-slate-600">No candidates found for this source.</p>
            </div>
          ) : (
            candidates.map((c) => (
              <CandidateCard
                key={c.id}
                candidate={c}
                isHovered={hoveredId === c.id}
                onHoverEnter={setHoveredId}
                onHoverLeave={() => setHoveredId(null)}
                onMark={handleMark}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
