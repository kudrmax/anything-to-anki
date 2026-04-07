import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Film, Loader2, Sparkles } from 'lucide-react'
import { api } from '@/api/client'
import type { CardPreview, CandidateStatus, GenerationQueueStatus, SourceDetail, StoredCandidate } from '@/api/types'
import { CandidateCardV2 as CandidateCard } from '@/components/CandidateCardV2'
import { TextAnnotator } from '@/components/TextAnnotator'

function sortCandidates(candidates: StoredCandidate[]): StoredCandidate[] {
  const cefrOrder: Record<string, number> = { A1: 0, A2: 1, B1: 2, B2: 3, C1: 4, C2: 5 }
  return [...candidates].sort((a, b) => {
    if (a.is_sweet_spot !== b.is_sweet_spot) return a.is_sweet_spot ? -1 : 1
    if (b.zipf_frequency !== a.zipf_frequency) return b.zipf_frequency - a.zipf_frequency
    return (cefrOrder[a.cefr_level ?? ''] ?? 0) - (cefrOrder[b.cefr_level ?? ''] ?? 0)
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
  const [editingFragmentFor, setEditingFragmentFor] = useState<number | null>(null)
  const candidatesPanelRef = useRef<HTMLDivElement>(null)
  const autoSaveRef = useRef(false)
  const textPanelRef = useRef<HTMLDivElement>(null)
  const hoverFromCardRef = useRef(false)
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [regeneratingMediaIds, setRegeneratingMediaIds] = useState<Set<number>>(new Set())
  const [genQueue, setGenQueue] = useState<GenerationQueueStatus | null>(null)
  const [toast, setToast] = useState<{ text: string; key: number } | null>(null)
  const [mediaMap, setMediaMap] = useState<Record<number, { screenshotUrl: string | null; audioUrl: string | null }>>({})
  const [mediaJob, setMediaJob] = useState<{ jobId: number; status: string; processed: number; total: number; failed: number } | null>(null)

  const runningJob = genQueue?.running_job ?? null
  const pendingJobsCount = genQueue?.pending_jobs.length ?? 0

  // IDs of candidates being processed right now (only running job)
  const processingCandidateIds = useMemo(
    () => new Set(runningJob?.candidate_ids ?? []),
    [runningJob]
  )

  // IDs of candidates in queue (all pending jobs)
  const queuedCandidateIds = useMemo(
    () => new Set(genQueue?.pending_jobs.flatMap(j => j.candidate_ids) ?? []),
    [genQueue]
  )

  useEffect(() => {
    const load = async () => {
      try {
        const [src, cands, queue, cards] = await Promise.all([
          api.getSource(sourceId),
          api.getCandidates(sourceId),
          api.getGenerationStatus(),
          api.getSourceCards(sourceId).catch(() => [] as CardPreview[]),
        ])
        setSource(src)
        setCandidates(sortCandidates(cands))
        if (queue) setGenQueue(queue)
        const map: Record<number, { screenshotUrl: string | null; audioUrl: string | null }> = {}
        for (const card of cards) {
          map[card.candidate_id] = { screenshotUrl: card.screenshot_url, audioUrl: card.audio_url }
        }
        setMediaMap(map)
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

  const handleEditFragment = useCallback((candidateId: number) => {
    setEditingFragmentFor(candidateId)
  }, [])

  const handleCancelEditFragment = useCallback(() => {
    setEditingFragmentFor(null)
  }, [])

  const handleSetFragment = useCallback(async (fragment: string) => {
    if (editingFragmentFor === null) return
    await api.updateCandidateFragment(editingFragmentFor, fragment)
    setCandidates((prev) =>
      prev.map((c) => (c.id === editingFragmentFor ? { ...c, context_fragment: fragment } : c)),
    )
    setEditingFragmentFor(null)
  }, [editingFragmentFor])

  const handleManualAdd = useCallback(async (surfaceForm: string, contextFragment: string) => {
    const candidate = await api.addManualCandidate(sourceId, surfaceForm, contextFragment)
    setCandidates((prev) => sortCandidates([...prev, candidate]))
  }, [sourceId])

  const handleWordClick = useCallback((candidateId: number) => {
    hoverFromCardRef.current = false
    const el = candidatesPanelRef.current?.querySelector(`[data-candidate-id="${candidateId}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHoveredId(candidateId)
    setTimeout(() => setHoveredId(null), 1500)
  }, [])

  const handleGenerate = useCallback(async (candidateId: number) => {
    setGeneratingIds((prev) => new Set(prev).add(candidateId))
    try {
      const res = await api.generateMeaning(candidateId)
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? {
          ...c,
          meaning: {
            meaning: res.meaning,
            ipa: res.ipa,
            status: 'done' as const,
            error: null,
            generated_at: null,
          },
        } : c)),
      )
      setToast({ text: `Tokens used: ${res.tokens_used}`, key: Date.now() })
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Generation failed', key: Date.now() })
    } finally {
      setGeneratingIds((prev) => {
        const next = new Set(prev)
        next.delete(candidateId)
        return next
      })
    }
  }, [])

  const handleStartGeneration = useCallback(async () => {
    try {
      const queue = await api.startGeneration(sourceId)
      setGenQueue(queue)
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Failed to start', key: Date.now() })
    }
  }, [sourceId])

  const handleRegenerateCandidateMedia = useCallback(async (candidateId: number) => {
    setRegeneratingMediaIds((prev) => new Set(prev).add(candidateId))
    try {
      await api.regenerateCandidateMedia(candidateId)
      // Reload candidates (so updated media_start_ms/end_ms are reflected)
      const [updatedCandidates, cards] = await Promise.all([
        api.getCandidates(sourceId),
        api.getSourceCards(sourceId).catch(() => []),
      ])
      setCandidates(sortCandidates(updatedCandidates))
      const map: Record<number, { screenshotUrl: string | null; audioUrl: string | null }> = {}
      for (const card of cards) {
        map[card.candidate_id] = { screenshotUrl: card.screenshot_url, audioUrl: card.audio_url }
      }
      setMediaMap(map)
      setToast({ text: 'Media regenerated', key: Date.now() })
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Regeneration failed', key: Date.now() })
    } finally {
      setRegeneratingMediaIds((prev) => {
        const next = new Set(prev)
        next.delete(candidateId)
        return next
      })
    }
  }, [sourceId])

  const handleStartMediaExtraction = useCallback(async () => {
    try {
      const res = await api.startMediaExtraction(sourceId)
      setMediaJob({ jobId: res.job_id, status: res.status, processed: 0, total: 0, failed: 0 })
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Failed to start media extraction', key: Date.now() })
    }
  }, [sourceId])

  const handleStopGeneration = useCallback(async () => {
    if (!runningJob) return
    try {
      await api.stopGeneration(runningJob.id)
      setGenQueue(prev => prev ? {
        ...prev,
        running_job: prev.running_job ? { ...prev.running_job, status: 'paused' } : null,
        pending_jobs: [],
      } : null)
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Failed to stop', key: Date.now() })
    }
  }, [runningJob])

  useEffect(() => {
    const hasActive = runningJob?.status === 'running' || runningJob?.status === 'pending' || pendingJobsCount > 0
    if (!hasActive) return
    const interval = setInterval(async () => {
      try {
        const updated = await api.getCandidates(sourceId)
        setCandidates(sortCandidates(updated))
        const queue = await api.getGenerationStatus()
        setGenQueue(queue)
        if (!queue || (!queue.running_job && queue.pending_jobs.length === 0)) {
          clearInterval(interval)
        }
      } catch { /* ignore polling errors */ }
    }, 10000)
    return () => clearInterval(interval)
  }, [runningJob?.status, pendingJobsCount, sourceId])

  useEffect(() => {
    if (!mediaJob) return
    if (mediaJob.status !== 'pending' && mediaJob.status !== 'running') return
    const interval = setInterval(async () => {
      try {
        const status = await api.getMediaExtractionStatus(sourceId, mediaJob.jobId)
        setMediaJob({
          jobId: mediaJob.jobId,
          status: status.status,
          processed: status.processed,
          total: status.total,
          failed: status.failed,
        })
        // Reload cards to pick up fresh media URLs when done
        if (status.status === 'done') {
          try {
            const cards = await api.getSourceCards(sourceId)
            const map: Record<number, { screenshotUrl: string | null; audioUrl: string | null }> = {}
            for (const card of cards) {
              map[card.candidate_id] = { screenshotUrl: card.screenshot_url, audioUrl: card.audio_url }
            }
            setMediaMap(map)
          } catch { /* ignore */ }
        }
      } catch {
        /* ignore polling errors */
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [mediaJob, sourceId])

  useEffect(() => {
    if (hoveredId === null || !hoverFromCardRef.current) return
    const mark = textPanelRef.current?.querySelector(`mark[data-candidate-id="${hoveredId}"]`)
    mark?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [hoveredId])

  useEffect(() => {
    if (loading) return
    if (!autoSaveRef.current) {
      autoSaveRef.current = true
      return
    }
    const anyPending = candidates.some((c) => c.status === 'pending')
    const newStatus = anyPending ? 'partially_reviewed' : 'reviewed'
    void api.updateSourceStatus(sourceId, newStatus)
  }, [candidates, loading, sourceId])

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

  const batchGenerationStatus: 'pending' | 'running' | 'failed' | null = (() => {
    if (!runningJob || (runningJob.source_id !== null && runningJob.source_id !== sourceId)) return null
    if (runningJob.status === 'pending' || runningJob.status === 'running' || runningJob.status === 'failed') {
      return runningJob.status
    }
    return null
  })()

  const editingCandidate = editingFragmentFor !== null
    ? candidates.find((c) => c.id === editingFragmentFor)
    : null

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
        </div>
      </header>

      {/* Split panels */}
      <div className="flex-1 overflow-hidden flex">
        {/* Left: candidates */}
        <div ref={candidatesPanelRef} className="w-[45%] overflow-y-auto p-4 flex flex-col gap-3" style={{ borderRight: '1px solid var(--glass-b)' }}>
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--td)' }}>
              Candidates {candidates.length > 0 && `(${candidates.length})`}
            </h2>
            <div className="flex items-center gap-2">
              {candidates.length > 0 && (
                runningJob && (runningJob.status === 'pending' || runningJob.status === 'running') ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs" style={{ color: 'var(--tm)' }}>
                      Generating... {runningJob.processed_candidates}/{runningJob.total_candidates}
                      {pendingJobsCount > 0 && ` (+${pendingJobsCount} batches queued)`}
                    </span>
                    <button
                      onClick={() => void handleStopGeneration()}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all hover:brightness-110 cursor-pointer"
                      style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', color: '#f87171' }}
                    >
                      Stop
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => void handleStartGeneration()}
                    disabled={generatingIds.size > 0}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
                    style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                  >
                    <Sparkles size={12} />
                    Generate Meanings
                  </button>
                )
              )}
              {source && source.source_type === 'video' && (
                mediaJob && (mediaJob.status === 'pending' || mediaJob.status === 'running') ? (
                  <span
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg"
                    style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                  >
                    <Loader2 size={12} className="animate-spin" />
                    {mediaJob.processed}/{mediaJob.total} media
                  </span>
                ) : mediaJob && mediaJob.status === 'done' ? (
                  <span
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg"
                    style={{ border: '1px solid rgba(16,185,129,.3)', color: 'rgba(16,185,129,.9)', background: 'rgba(16,185,129,.1)' }}
                  >
                    ✓ Media ready{mediaJob.failed > 0 ? ` (${mediaJob.failed} failed)` : ''}
                  </span>
                ) : mediaJob && mediaJob.status === 'failed' ? (
                  <span
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg"
                    style={{ border: '1px solid rgba(244,63,94,.3)', color: 'rgba(244,63,94,.9)', background: 'rgba(244,63,94,.1)' }}
                  >
                    ✗ Media failed
                  </span>
                ) : (
                  <button
                    onClick={() => void handleStartMediaExtraction()}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all hover:brightness-110 cursor-pointer"
                    style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                  >
                    <Film size={12} />
                    Generate Media
                  </button>
                )
              )}
            </div>
          </div>

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
                onEditFragment={handleEditFragment}
                onCancelEditFragment={handleCancelEditFragment}
                isEditingFragment={editingFragmentFor === c.id}
                onGenerateMeaning={(id) => void handleGenerate(id)}
                isGenerating={generatingIds.has(c.id)}
                batchGenerationStatus={batchGenerationStatus}
                isInBatchProcessing={processingCandidateIds.has(c.id)}
                isQueued={queuedCandidateIds.has(c.id)}
                screenshotUrl={mediaMap[c.id]?.screenshotUrl}
                audioUrl={mediaMap[c.id]?.audioUrl}
                onRegenerateMedia={source?.source_type === 'video' ? (id) => void handleRegenerateCandidateMedia(id) : undefined}
                isRegeneratingMedia={regeneratingMediaIds.has(c.id)}
                hasMediaTimecodes={c.media?.start_ms != null}
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
                  onEditFragment={handleEditFragment}
                  onCancelEditFragment={handleCancelEditFragment}
                  isEditingFragment={editingFragmentFor === c.id}
                  onGenerateMeaning={(id) => void handleGenerate(id)}
                  isGenerating={generatingIds.has(c.id)}
                  batchGenerationStatus={batchGenerationStatus}
                  isInBatchProcessing={processingCandidateIds.has(c.id)}
                  isQueued={queuedCandidateIds.has(c.id)}
                  screenshotUrl={mediaMap[c.id]?.screenshotUrl}
                  audioUrl={mediaMap[c.id]?.audioUrl}
                  onRegenerateMedia={source?.source_type === 'video' ? (id) => void handleRegenerateCandidateMedia(id) : undefined}
                  isRegeneratingMedia={regeneratingMediaIds.has(c.id)}
                  hasMediaTimecodes={c.media?.start_ms != null}
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

          {editingFragmentFor !== null && (
            <div
              className="mb-4 flex items-center justify-between rounded-lg px-3 py-2 text-xs"
              style={{ background: 'var(--abg)', border: '1px solid var(--ag)' }}
            >
              <span style={{ color: 'var(--accent)' }}>
                ✏ Selecting boundary for:{' '}
                <strong>{editingCandidate?.lemma ?? '…'}</strong>
              </span>
              <button
                onClick={handleCancelEditFragment}
                className="cursor-pointer transition-opacity hover:opacity-100"
                style={{ color: 'var(--tm)', opacity: 0.7 }}
              >
                Cancel
              </button>
            </div>
          )}

          <TextAnnotator
            text={annotationText}
            candidates={candidates}
            hoveredCandidateId={hoveredId}
            ratedIds={ratedIds}
            onWordClick={handleWordClick}
            onWordHover={handleTextHover}
            onManualAdd={handleManualAdd}
            editingFragmentFor={editingFragmentFor}
            editingFragmentLemma={editingCandidate?.lemma ?? null}
            onSetFragment={handleSetFragment}
          />
        </div>
      </div>

      {toast && <Toast key={toast.key} text={toast.text} onDone={() => setToast(null)} />}
    </div>
  )
}

function Toast({ text, onDone }: { text: string; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 3000)
    return () => clearTimeout(timer)
  }, [onDone])

  return (
    <div
      className="fixed bottom-4 right-4 rounded-lg px-4 py-2.5 text-xs font-medium shadow-lg"
      style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
    >
      {text}
    </div>
  )
}
