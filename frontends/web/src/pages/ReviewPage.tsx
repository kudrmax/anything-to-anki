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
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  if (!source) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm" style={{ color: 'var(--td)' }}>Source not found.</p>
      </div>
    )
  }

  const markedCount = candidates.filter((c) => c.status !== 'pending').length
  const learnCount = candidates.filter((c) => c.status === 'learn').length
  const progress = candidates.length > 0 ? (markedCount / candidates.length) * 100 : 0
  const annotationText = source.cleaned_text ?? source.raw_text

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Page sub-header */}
      <header
        className="shrink-0 px-6 py-3 flex items-center justify-between gap-4"
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

        <div className="flex-1 max-w-sm">
          <div className="flex items-center justify-between text-xs mb-1" style={{ color: 'var(--tm)' }}>
            <span>Marked: {markedCount} / {candidates.length}</span>
            <span style={{ color: 'var(--td)' }}>To learn: {learnCount}</span>
          </div>
          <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--glass-b)' }}>
            <div
              className="h-full transition-all duration-300"
              style={{ width: `${progress}%`, background: 'var(--grad)' }}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(`/sources/${sourceId}/export`)}
            className="rounded-lg px-4 py-1.5 text-sm font-medium transition-all cursor-pointer hover:brightness-110"
            style={{
              border:  '1px solid var(--ag)',
              color:   'var(--accent)',
              background: 'var(--abg)',
            }}
          >
            Export →
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
            style={{ background: 'var(--accent)' }}
          >
            {saving && <Loader2 size={12} className="animate-spin" />}
            Save and exit
          </button>
        </div>
      </header>

      {/* Split panels */}
      <div className="flex-1 overflow-hidden flex">
        {/* Left: text */}
        <div className="w-[55%] overflow-y-auto p-6" style={{ borderRight: '1px solid var(--glass-b)' }}>
          <h2 className="text-xs font-medium uppercase tracking-wider mb-4" style={{ color: 'var(--td)' }}>
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
          <h2 className="text-xs font-medium uppercase tracking-wider px-1" style={{ color: 'var(--td)' }}>
            Candidates {candidates.length > 0 && `(${candidates.length})`}
          </h2>
          {candidates.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center" style={{ borderColor: 'var(--glass-b)' }}>
              <p className="text-sm" style={{ color: 'var(--td)' }}>No candidates found for this source.</p>
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
