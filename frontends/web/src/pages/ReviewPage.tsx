import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  const candidatesPanelRef = useRef<HTMLDivElement>(null)
  const textPanelRef = useRef<HTMLDivElement>(null)
  const hoverFromCardRef = useRef(false)

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

  const handleCardHoverEnter = useCallback((id: number) => {
    hoverFromCardRef.current = true
    setHoveredId(id)
  }, [])

  const handleTextHover = useCallback((id: number | null) => {
    hoverFromCardRef.current = false
    setHoveredId(id)
  }, [])

  const handleWordClick = useCallback((candidateId: number) => {
    hoverFromCardRef.current = false
    const el = candidatesPanelRef.current?.querySelector(`[data-candidate-id="${candidateId}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    setHoveredId(candidateId)
    setTimeout(() => setHoveredId(null), 1500)
  }, [])

  useEffect(() => {
    if (hoveredId === null || !hoverFromCardRef.current) return
    const mark = textPanelRef.current?.querySelector(`mark[data-candidate-id="${hoveredId}"]`)
    mark?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [hoveredId])

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

  const pendingCandidates = useMemo(
    () => candidates.filter((c) => c.status === 'pending'),
    [candidates],
  )
  const ratedCandidates = useMemo(
    () => candidates.filter((c) => c.status !== 'pending'),
    [candidates],
  )
  const ratedIds = useMemo(
    () => new Set(ratedCandidates.map((c) => c.id)),
    [ratedCandidates],
  )

  const markedCount = ratedCandidates.length
  const learnCount = candidates.filter((c) => c.status === 'learn').length
  const progress = candidates.length > 0 ? (markedCount / candidates.length) * 100 : 0

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
        {/* Left: candidates */}
        <div ref={candidatesPanelRef} className="w-[45%] overflow-y-auto p-4 flex flex-col gap-3" style={{ borderRight: '1px solid var(--glass-b)' }}>
          <h2 className="text-xs font-medium uppercase tracking-wider px-1" style={{ color: 'var(--td)' }}>
            Candidates {candidates.length > 0 && `(${candidates.length})`}
          </h2>

          {candidates.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center" style={{ borderColor: 'var(--glass-b)' }}>
              <p className="text-sm" style={{ color: 'var(--td)' }}>No candidates found for this source.</p>
            </div>
          ) : pendingCandidates.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center" style={{ borderColor: 'var(--glass-b)' }}>
              <p className="text-sm" style={{ color: 'var(--td)' }}>All candidates reviewed.</p>
            </div>
          ) : (
            pendingCandidates.map((c) => (
              <CandidateCard
                key={c.id}
                candidate={c}
                isRated={false}
                isHovered={hoveredId === c.id}
                onHoverEnter={handleCardHoverEnter}
                onHoverLeave={() => setHoveredId(null)}
                onMark={handleMark}
              />
            ))
          )}

          {ratedCandidates.length > 0 && (
            <>
              <div className="flex items-center gap-2 px-1 pt-1">
                <div className="flex-1 h-px" style={{ background: 'var(--glass-b)' }} />
                <span className="text-xs font-medium uppercase tracking-wider shrink-0" style={{ color: 'var(--td)' }}>
                  Reviewed ({ratedCandidates.length})
                </span>
                <div className="flex-1 h-px" style={{ background: 'var(--glass-b)' }} />
              </div>
              {ratedCandidates.map((c) => (
                <CandidateCard
                  key={c.id}
                  candidate={c}
                  isRated={true}
                  isHovered={hoveredId === c.id}
                  onHoverEnter={handleCardHoverEnter}
                  onHoverLeave={() => setHoveredId(null)}
                  onMark={handleMark}
                />
              ))}
            </>
          )}
        </div>

        {/* Right: text */}
        <div ref={textPanelRef} className="flex-1 overflow-y-auto p-6">
          <h2 className="text-xs font-medium uppercase tracking-wider mb-4" style={{ color: 'var(--td)' }}>
            Source text
          </h2>
          <TextAnnotator
            text={annotationText}
            candidates={candidates}
            hoveredCandidateId={hoveredId}
            ratedIds={ratedIds}
            onWordClick={handleWordClick}
            onWordHover={handleTextHover}
          />
        </div>
      </div>
    </div>
  )
}
