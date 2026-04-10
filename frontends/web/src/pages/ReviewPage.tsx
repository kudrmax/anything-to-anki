import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Film, Loader2, Sparkles } from 'lucide-react'
import { api } from '@/api/client'
import type {
  CandidateSortOrder,
  CandidateStatus,
  CardPreview,
  FollowUpAction,
  QueueSummary,
  SourceDetail,
  StoredCandidate,
} from '@/api/types'
import { CandidateCardV2 as CandidateCard } from '@/components/CandidateCardV2'
import { TextAnnotator } from '@/components/TextAnnotator'
import { TextSelectionPopover } from '@/components/TextSelectionPopover'
import { autoPlayAudioPref } from '@/lib/preferences'

const VPN_ERROR_MARKER = 'Blocked country'

function isVpnError(e: unknown): boolean {
  return e instanceof Error && e.message.includes(VPN_ERROR_MARKER)
}

function hasCandidateVpnErrors(candidates: StoredCandidate[]): boolean {
  return candidates.some(
    (c) => c.meaning?.status === 'failed' && c.meaning.error?.includes(VPN_ERROR_MARKER),
  )
}

function audioUrlForCandidate(candidate: StoredCandidate, sourceId: number): string | null {
  const path = candidate.media?.audio_path
  if (!path) return null
  return `/media/${sourceId}/${path.split('/').pop()}`
}

export function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const sourceId = Number(id)

  const [source, setSource] = useState<SourceDetail | null>(null)
  const [candidates, setCandidates] = useState<StoredCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [hoveredId, setHoveredId] = useState<number | null>(null)
  const candidatesPanelRef = useRef<HTMLDivElement>(null)
  const autoSaveRef = useRef(false)
  const textPanelRef = useRef<HTMLDivElement>(null)
  const hoverFromCardRef = useRef(false)
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [regeneratingMediaIds, setRegeneratingMediaIds] = useState<Set<number>>(new Set())
  const [queueSummary, setQueueSummary] = useState<QueueSummary | null>(null)
  const [toast, setToast] = useState<{ text: string; key: number } | null>(null)
  const [vpnBlocked, setVpnBlocked] = useState(false)
  const [downloadingVideo, setDownloadingVideo] = useState(false)
  const [mediaMap, setMediaMap] = useState<Record<number, { screenshotUrl: string | null; audioUrl: string | null }>>({})
  const [sortOrder, setSortOrder] = useState<CandidateSortOrder>(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem('reviewPage.sortOrder') : null
    return saved === 'chronological' || saved === 'relevance' ? saved : 'relevance'
  })

  type InteractionMode =
    | { type: 'idle' }
    | { type: 'adding' }
    | { type: 'editing'; candidateId: number; lemma: string; pos: string; originalFragment: string }

  const [interactionMode, setInteractionMode] = useState<InteractionMode>({ type: 'idle' })
  const [popoverState, setPopoverState] = useState<{
    phrase: string
    position: { x: number; y: number; yBottom: number }
  } | null>(null)
  const [flashCandidateId, setFlashCandidateId] = useState<number | null>(null)

  useEffect(() => {
    localStorage.setItem('reviewPage.sortOrder', sortOrder)
  }, [sortOrder])

  // Audio playback is owned by ReviewPage so that:
  // - only one audio plays at a time across cards
  // - the parent can auto-play the next card after a mark click
  const [playingCandidateId, setPlayingCandidateId] = useState<number | null>(null)
  const audioElRef = useRef<HTMLAudioElement | null>(null)

  const stopAudio = useCallback(() => {
    if (audioElRef.current) {
      audioElRef.current.pause()
      audioElRef.current.currentTime = 0
      audioElRef.current = null
    }
    setPlayingCandidateId(null)
  }, [])

  const playAudio = useCallback((candidateId: number, url: string) => {
    if (audioElRef.current) {
      audioElRef.current.pause()
      audioElRef.current = null
    }
    const audio = new Audio(url)
    audioElRef.current = audio
    const clear = () => {
      if (audioElRef.current === audio) {
        audioElRef.current = null
        setPlayingCandidateId(null)
      }
    }
    audio.addEventListener('ended', clear)
    audio.addEventListener('error', clear)
    audio.play()
      .then(() => setPlayingCandidateId(candidateId))
      .catch(() => clear())
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioElRef.current) {
        audioElRef.current.pause()
        audioElRef.current = null
      }
    }
  }, [])

  const loadCandidates = useCallback(async () => {
    const [cands, cards] = await Promise.all([
      api.getCandidates(sourceId, sortOrder),
      api.getSourceCards(sourceId).catch(() => [] as CardPreview[]),
    ])
    setCandidates(cands)
    if (hasCandidateVpnErrors(cands)) setVpnBlocked(true)
    const map: Record<number, { screenshotUrl: string | null; audioUrl: string | null }> = {}
    for (const card of cards) {
      map[card.candidate_id] = { screenshotUrl: card.screenshot_url, audioUrl: card.audio_url }
    }
    setMediaMap(map)
  }, [sourceId, sortOrder])

  const loadQueueSummary = useCallback(async () => {
    try {
      const summary = await api.getQueueSummary(sourceId)
      setQueueSummary(summary)
    } catch {
      // ignore — endpoint may not be available for all source types
    }
  }, [sourceId])

  useEffect(() => {
    const load = async () => {
      try {
        const src = await api.getSource(sourceId, sortOrder)
        setSource(src)
        setCandidates(src.candidates)
        await Promise.all([
          api.getSourceCards(sourceId).catch(() => [] as CardPreview[]).then((cards) => {
            const map: Record<number, { screenshotUrl: string | null; audioUrl: string | null }> = {}
            for (const card of cards) {
              map[card.candidate_id] = { screenshotUrl: card.screenshot_url, audioUrl: card.audio_url }
            }
            setMediaMap(map)
          }),
          loadQueueSummary(),
        ])
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [sourceId, sortOrder, loadQueueSummary])

  // Polling while there are inflight jobs
  useEffect(() => {
    const meaningInflight = (queueSummary?.meaning.queued ?? 0) + (queueSummary?.meaning.running ?? 0)
    const mediaInflight = (queueSummary?.media.queued ?? 0) + (queueSummary?.media.running ?? 0)
    if (meaningInflight + mediaInflight === 0) return

    const interval = setInterval(() => {
      void loadCandidates()
      void loadQueueSummary()
    }, 3000)
    return () => clearInterval(interval)
  }, [queueSummary, loadCandidates, loadQueueSummary])

  // Keep a ref to the latest candidates so handleMark (memoized) can read
  // the freshest list without re-creating on every state change.
  const candidatesRef = useRef<StoredCandidate[]>(candidates)
  candidatesRef.current = candidates

  const handleMark = useCallback(async (candidateId: number, status: CandidateStatus) => {
    // Stop any currently-playing audio (manual or auto-play). The user
    // pressed a mark button, so they're done listening.
    stopAudio()

    // Capture the next pending candidate BEFORE marking — once we mark,
    // this one is removed from the pending list and 'next' shifts.
    const pending = candidatesRef.current.filter((c) => c.status === 'pending')
    const idx = pending.findIndex((c) => c.id === candidateId)
    const nextPending = idx >= 0 && idx + 1 < pending.length ? pending[idx + 1] : null

    let nextToPlay: { id: number; url: string } | null = null
    if (nextPending && autoPlayAudioPref.read()) {
      const url = audioUrlForCandidate(nextPending, sourceId)
      if (url && nextPending.id !== null) {
        nextToPlay = { id: nextPending.id, url }
      }
    }

    await api.markCandidate(candidateId, status)
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, status } : c)),
    )

    // Sync right panel context to the next pending candidate
    hoverFromCardRef.current = true
    setHoveredId(nextPending?.id ?? null)

    if (nextToPlay) {
      playAudio(nextToPlay.id, nextToPlay.url)
    }
  }, [sourceId, playAudio, stopAudio])

  const handleCardHoverEnter = useCallback((id: number) => {
    hoverFromCardRef.current = true
    setHoveredId(id)
  }, [])

  const handleTextHover = useCallback((id: number | null) => {
    hoverFromCardRef.current = false
    setHoveredId(id)
  }, [])

  const handleStartAdding = useCallback(() => {
    setInteractionMode({ type: 'adding' })
    setPopoverState(null)
  }, [])

  const handleStartEditing = useCallback((candidateId: number) => {
    const candidate = candidatesRef.current.find(c => c.id === candidateId)
    if (!candidate) return
    setInteractionMode({
      type: 'editing',
      candidateId,
      lemma: candidate.lemma,
      pos: candidate.pos,
      originalFragment: candidate.context_fragment,
    })
    setPopoverState(null)
  }, [])

  const handleCancelMode = useCallback(() => {
    setInteractionMode({ type: 'idle' })
    setPopoverState(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  const handleTextSelected = useCallback((
    phrase: string,
    position: { x: number; y: number; yBottom: number },
  ) => {
    if (interactionMode.type === 'idle') return
    setPopoverState({ phrase, position })
  }, [interactionMode.type])

  const handlePopoverCancel = useCallback(() => {
    setPopoverState(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  const handleSetBoundary = useCallback(async (phrase: string) => {
    if (interactionMode.type !== 'editing') return
    await api.updateCandidateFragment(interactionMode.candidateId, phrase)
    setCandidates(prev =>
      prev.map(c => c.id === interactionMode.candidateId ? { ...c, context_fragment: phrase } : c),
    )
    setInteractionMode({ type: 'idle' })
    setPopoverState(null)
    window.getSelection()?.removeAllRanges()
  }, [interactionMode])

  const handleAddWord = useCallback(async (target: string, context: string) => {
    const result = await api.addManualCandidate(sourceId, target, context)
    setInteractionMode({ type: 'idle' })
    setPopoverState(null)
    window.getSelection()?.removeAllRanges()
    await loadCandidates()
    setFlashCandidateId(result.id)
  }, [sourceId, loadCandidates])

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
            translation: res.translation,
            synonyms: res.synonyms,
            examples: res.examples,
            ipa: res.ipa,
            status: 'done' as const,
            error: null,
            generated_at: null,
          },
        } : c)),
      )
      setToast({ text: `Tokens used: ${res.tokens_used}`, key: Date.now() })
    } catch (e) {
      if (isVpnError(e)) setVpnBlocked(true)
      else setToast({ text: e instanceof Error ? e.message : 'Generation failed', key: Date.now() })
    } finally {
      setGeneratingIds((prev) => {
        const next = new Set(prev)
        next.delete(candidateId)
        return next
      })
    }
  }, [])

  const handleFollowUp = useCallback(async (candidateId: number, action: FollowUpAction, text?: string) => {
    setGeneratingIds((prev) => new Set(prev).add(candidateId))
    try {
      const res = await api.generateMeaning(candidateId, action, text)
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? {
          ...c,
          meaning: {
            meaning: res.meaning,
            translation: res.translation,
            synonyms: res.synonyms,
            examples: res.examples,
            ipa: res.ipa,
            status: 'done' as const,
            error: null,
            generated_at: null,
          },
        } : c)),
      )
      setToast({ text: `Tokens used: ${res.tokens_used}`, key: Date.now() })
    } catch (e) {
      if (isVpnError(e)) setVpnBlocked(true)
      else setToast({ text: e instanceof Error ? e.message : 'Follow-up failed', key: Date.now() })
    } finally {
      setGeneratingIds((prev) => {
        const next = new Set(prev)
        next.delete(candidateId)
        return next
      })
    }
  }, [])

  const handleGenerateMeanings = useCallback(async () => {
    try {
      await api.enqueueMeaningGeneration(sourceId, sortOrder)
      await loadCandidates()
      await loadQueueSummary()
    } catch (e) {
      if (isVpnError(e)) setVpnBlocked(true)
      else setToast({ text: e instanceof Error ? e.message : 'Failed to enqueue meanings', key: Date.now() })
    }
  }, [sourceId, sortOrder, loadCandidates, loadQueueSummary])

  const handleGenerateMedia = useCallback(async () => {
    try {
      await api.enqueueMediaGeneration(sourceId, sortOrder)
      await loadCandidates()
      await loadQueueSummary()
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Failed to enqueue media', key: Date.now() })
    }
  }, [sourceId, sortOrder, loadCandidates, loadQueueSummary])

  const handleCancelMeanings = useCallback(async () => {
    try {
      await api.cancelMeaningQueue(sourceId)
      await loadCandidates()
      await loadQueueSummary()
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Failed to cancel', key: Date.now() })
    }
  }, [sourceId, loadCandidates, loadQueueSummary])

  const handleCancelMedia = useCallback(async () => {
    try {
      await api.cancelMediaQueue(sourceId)
      await loadCandidates()
      await loadQueueSummary()
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Failed to cancel', key: Date.now() })
    }
  }, [sourceId, loadCandidates, loadQueueSummary])

  const handleRetryFailedMeanings = useCallback(async () => {
    try {
      await api.retryFailedMeanings(sourceId)
      await loadCandidates()
      await loadQueueSummary()
    } catch (e) {
      if (isVpnError(e)) setVpnBlocked(true)
      else setToast({ text: e instanceof Error ? e.message : 'Failed to retry', key: Date.now() })
    }
  }, [sourceId, loadCandidates, loadQueueSummary])

  const handleRetryFailedMedia = useCallback(async () => {
    try {
      await api.retryFailedMedia(sourceId)
      await loadCandidates()
      await loadQueueSummary()
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : 'Failed to retry', key: Date.now() })
    }
  }, [sourceId, loadCandidates, loadQueueSummary])

  const handleRegenerateCandidateMedia = useCallback(async (candidateId: number) => {
    setRegeneratingMediaIds((prev) => new Set(prev).add(candidateId))
    try {
      await api.regenerateCandidateMedia(candidateId)
      await loadCandidates()
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
  }, [loadCandidates])

  useEffect(() => {
    if (hoveredId === null || !hoverFromCardRef.current) return
    const mark = textPanelRef.current?.querySelector(`mark[data-candidate-id="${hoveredId}"]`)
    mark?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [hoveredId])

  // Auto-save source status only when the derived status actually changes,
  // not on every candidates re-fetch (which happens during polling).
  const lastSavedStatusRef = useRef<string | null>(null)
  useEffect(() => {
    if (loading) return
    const anyPending = candidates.some((c) => c.status === 'pending')
    const newStatus = anyPending ? 'partially_reviewed' : 'reviewed'
    if (!autoSaveRef.current) {
      autoSaveRef.current = true
      lastSavedStatusRef.current = newStatus
      return
    }
    if (lastSavedStatusRef.current === newStatus) return
    lastSavedStatusRef.current = newStatus
    void api.updateSourceStatus(sourceId, newStatus)
  }, [candidates, loading, sourceId])

  useEffect(() => {
    if (interactionMode.type === 'idle') return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !popoverState) {
        handleCancelMode()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [interactionMode.type, popoverState, handleCancelMode])

  useEffect(() => {
    if (flashCandidateId === null) return
    const timer = setTimeout(() => {
      const el = candidatesPanelRef.current?.querySelector(
        `[data-candidate-id="${flashCandidateId}"]`,
      ) as HTMLElement | null
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        // Wait for scroll to finish before starting flash
        setTimeout(() => {
          el.classList.add('card-flash')
          el.addEventListener('animationend', () => {
            el.classList.remove('card-flash')
          }, { once: true })
        }, 500)
      }
      setFlashCandidateId(null)
    }, 100)
    return () => clearTimeout(timer)
  }, [flashCandidateId])

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

  const hasInflightMeaning = ((queueSummary?.meaning.queued ?? 0) + (queueSummary?.meaning.running ?? 0)) > 0
  const hasFailedMeaning = (queueSummary?.meaning.failed ?? 0) > 0
  const hasInflightMedia = ((queueSummary?.media.queued ?? 0) + (queueSummary?.media.running ?? 0)) > 0
  const hasFailedMedia = (queueSummary?.media.failed ?? 0) > 0

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
      {/* Unified toolbar */}
      <header
        className="shrink-0 px-4 py-2 flex items-center gap-3"
        style={{ borderBottom: '1px solid var(--glass-b)' }}
      >
        {/* Back */}
        <button
          onClick={() => navigate('/')}
          className="text-sm transition-opacity hover:opacity-100 cursor-pointer"
          style={{ color: 'var(--tm)', opacity: 0.7 }}
        >
          ←
        </button>

        {/* Progress */}
        <span className="text-xs tabular-nums" style={{ color: 'var(--tm)' }}>
          {markedCount} / {candidates.length}
        </span>
        <div
          className="h-1 rounded-full overflow-hidden"
          style={{ width: 80, background: 'var(--glass-b)' }}
        >
          <div
            className="h-full transition-all duration-300"
            style={{ width: `${progress}%`, background: 'var(--grad)' }}
          />
        </div>
        <span className="text-xs" style={{ color: 'var(--td)' }}>
          learn: {learnCount}
        </span>

        {/* Sort toggle */}
        {candidates.length > 0 && (
          <div className="flex p-[2px] rounded-md" style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)' }}>
            <button
              onClick={() => setSortOrder('relevance')}
              className="px-2 py-[2px] rounded-[5px] text-[10px] font-medium transition-all cursor-pointer"
              style={
                sortOrder === 'relevance'
                  ? { background: 'var(--accent)', color: '#fff' }
                  : { background: 'transparent', color: 'var(--tm)' }
              }
              title="Sort by relevance"
            >
              A↓
            </button>
            <button
              onClick={() => setSortOrder('chronological')}
              className="px-2 py-[2px] rounded-[5px] text-[10px] font-medium transition-all cursor-pointer"
              style={
                sortOrder === 'chronological'
                  ? { background: 'var(--accent)', color: '#fff' }
                  : { background: 'transparent', color: 'var(--tm)' }
              }
              title="Sort chronologically"
            >
              T↓
            </button>
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Generate Meanings button */}
        {candidates.length > 0 && (
          hasInflightMeaning ? (
            <div className="flex items-center gap-2">
              <span className="text-xs flex items-center gap-1.5" style={{ color: 'var(--tm)' }}>
                <Loader2 size={12} className="animate-spin" />
                Meanings ({(queueSummary?.meaning.queued ?? 0) + (queueSummary?.meaning.running ?? 0)})
              </span>
              <button
                onClick={() => void handleCancelMeanings()}
                className="text-xs px-2 py-1 rounded-lg transition-all hover:brightness-110 cursor-pointer"
                style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--error)' }}
              >
                Cancel
              </button>
            </div>
          ) : hasFailedMeaning ? (
            <button
              onClick={() => void handleRetryFailedMeanings()}
              className="text-xs px-2 py-1 rounded-lg transition-all hover:brightness-110 cursor-pointer"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: 'var(--error)' }}
            >
              Retry meanings ({queueSummary?.meaning.failed})
            </button>
          ) : (
            <button
              onClick={() => void handleGenerateMeanings()}
              disabled={generatingIds.size > 0}
              className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
              style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
            >
              <Sparkles size={12} />
              Meanings
            </button>
          )
        )}

        {/* Download Media button (YouTube source without downloaded video) */}
        {source && source.content_type === 'video' && !source.video_downloaded && (
          downloadingVideo ? (
            <span className="text-xs flex items-center gap-1.5" style={{ color: 'var(--tm)' }}>
              <Loader2 size={12} className="animate-spin" />
              Downloading video…
            </span>
          ) : (
            <button
              onClick={async () => {
                setDownloadingVideo(true)
                try {
                  await api.downloadVideo(source.id)
                  const poll = setInterval(() => {
                    void api.getSource(sourceId, sortOrder).then((updated) => {
                      setSource(updated)
                      if (updated.video_downloaded) {
                        clearInterval(poll)
                        setDownloadingVideo(false)
                      }
                    }).catch(() => undefined)
                  }, 3000)
                } catch {
                  setDownloadingVideo(false)
                }
              }}
              className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg transition-all hover:brightness-110 cursor-pointer"
              style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
            >
              <Film size={12} />
              Download Media
            </button>
          )
        )}

        {/* Generate Media button (video only, after video is downloaded) */}
        {source && source.content_type === 'video' && source.video_downloaded && (
          hasInflightMedia ? (
            <div className="flex items-center gap-2">
              <span className="text-xs flex items-center gap-1.5" style={{ color: 'var(--tm)' }}>
                <Loader2 size={12} className="animate-spin" />
                Media ({(queueSummary?.media.queued ?? 0) + (queueSummary?.media.running ?? 0)})
              </span>
              <button
                onClick={() => void handleCancelMedia()}
                className="text-xs px-2 py-1 rounded-lg transition-all hover:brightness-110 cursor-pointer"
                style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--error)' }}
              >
                Cancel
              </button>
            </div>
          ) : hasFailedMedia ? (
            <button
              onClick={() => void handleRetryFailedMedia()}
              className="text-xs px-2 py-1 rounded-lg transition-all hover:brightness-110 cursor-pointer"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: 'var(--error)' }}
            >
              Retry media ({queueSummary?.media.failed})
            </button>
          ) : (
            <button
              onClick={() => void handleGenerateMedia()}
              className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg transition-all hover:brightness-110 cursor-pointer"
              style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
            >
              <Film size={12} />
              Media
            </button>
          )
        )}

        {/* Separator */}
        <div className="h-4 w-px" style={{ background: 'var(--glass-b)' }} />

        {/* Add button / mode banner */}
        {interactionMode.type === 'idle' ? (
          <button
            onClick={handleStartAdding}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-all hover:brightness-110 cursor-pointer"
            style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
          >
            + Add
          </button>
        ) : interactionMode.type === 'adding' ? (
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium" style={{ color: 'var(--accent)' }}>
              Select phrase in text to add
            </span>
            <button
              onClick={handleCancelMode}
              className="text-xs px-2 py-1 rounded-lg cursor-pointer transition-opacity hover:opacity-100"
              style={{ color: 'var(--td)', opacity: 0.7 }}
            >
              Cancel
            </button>
          </div>
        ) : interactionMode.type === 'editing' ? (
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium" style={{ color: 'var(--accent)' }}>
              Select new boundary for <strong>{interactionMode.lemma}</strong>
            </span>
            <button
              onClick={handleCancelMode}
              className="text-xs px-2 py-1 rounded-lg cursor-pointer transition-opacity hover:opacity-100"
              style={{ color: 'var(--td)', opacity: 0.7 }}
            >
              Cancel
            </button>
          </div>
        ) : null}

        {/* Separator */}
        <div className="h-4 w-px" style={{ background: 'var(--glass-b)' }} />

        {/* Export */}
        <button
          onClick={() => navigate(`/sources/${sourceId}/export`)}
          className="rounded-lg px-3 py-1 text-xs font-medium transition-all cursor-pointer hover:brightness-110"
          style={{
            border: '1px solid var(--ag)',
            color: 'var(--accent)',
            background: 'var(--abg)',
          }}
        >
          Export →
        </button>
      </header>

      {vpnBlocked && (
        <div
          className="shrink-0 px-4 py-2.5 flex items-center justify-between text-xs font-medium"
          style={{ background: 'rgba(239,68,68,.15)', borderBottom: '1px solid rgba(239,68,68,.3)', color: 'var(--error)' }}
        >
          <span>AI unavailable — turn on VPN</span>
          <button
            onClick={() => setVpnBlocked(false)}
            className="ml-4 opacity-60 hover:opacity-100 cursor-pointer"
            style={{ color: 'var(--error)' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Split panels */}
      <div className="flex-1 overflow-hidden flex">
        {/* Left: candidates */}
        <div
          ref={candidatesPanelRef}
          className="overflow-y-auto p-4 flex flex-col gap-3"
          style={{
            width: 'clamp(360px, 832px, 60vw)',
            flexShrink: 0,
            borderRight: '1px solid var(--glass-b)',
            opacity: interactionMode.type !== 'idle' ? 0.4 : 1,
            transition: 'opacity 200ms ease',
            pointerEvents: interactionMode.type !== 'idle' ? 'none' : 'auto',
          }}
        >

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
                sourceId={sourceId}
                isRated={false}
                isHovered={hoveredId === c.id}
                onHoverEnter={handleCardHoverEnter}
                onHoverLeave={() => setHoveredId(null)}
                onMark={handleMark}
                onEditFragment={handleStartEditing}
                onCancelEditFragment={handleCancelMode}
                isEditingFragment={interactionMode.type === 'editing' && interactionMode.candidateId === c.id}
                onGenerateMeaning={(id) => void handleGenerate(id)}
                isGenerating={generatingIds.has(c.id)}
                onFollowUp={(id, action, text) => void handleFollowUp(id, action, text)}
                screenshotUrl={mediaMap[c.id]?.screenshotUrl}
                audioUrl={mediaMap[c.id]?.audioUrl}
                onRegenerateMedia={source?.content_type === 'video' ? (id) => void handleRegenerateCandidateMedia(id) : undefined}
                isRegeneratingMedia={regeneratingMediaIds.has(c.id)}
                hasMediaTimecodes={c.media?.start_ms != null}
                isAudioPlaying={playingCandidateId === c.id}
                onPlayAudio={(url) => playAudio(c.id, url)}
                onStopAudio={stopAudio}
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
                  sourceId={sourceId}
                  isRated={true}
                  isHovered={hoveredId === c.id}
                  onHoverEnter={handleCardHoverEnter}
                  onHoverLeave={() => setHoveredId(null)}
                  onMark={handleMark}
                  onEditFragment={handleStartEditing}
                  onCancelEditFragment={handleCancelMode}
                  isEditingFragment={interactionMode.type === 'editing' && interactionMode.candidateId === c.id}
                  onGenerateMeaning={(id) => void handleGenerate(id)}
                  isGenerating={generatingIds.has(c.id)}
                  screenshotUrl={mediaMap[c.id]?.screenshotUrl}
                  audioUrl={mediaMap[c.id]?.audioUrl}
                  onRegenerateMedia={source?.content_type === 'video' ? (id) => void handleRegenerateCandidateMedia(id) : undefined}
                  isRegeneratingMedia={regeneratingMediaIds.has(c.id)}
                  hasMediaTimecodes={c.media?.start_ms != null}
                  isAudioPlaying={playingCandidateId === c.id}
                  onPlayAudio={(url) => playAudio(c.id, url)}
                  onStopAudio={stopAudio}
                />
              ))}
            </>
          )}
        </div>

        {/* Right: text */}
        <div
          ref={textPanelRef}
          className="flex-1 overflow-y-auto p-6"
          style={{
            ...(interactionMode.type !== 'idle' && {
              boxShadow: 'inset 0 0 20px rgba(139,92,246,0.05)',
              outline: '1.5px solid rgba(139,92,246,0.3)',
            }),
          }}
        >
          <TextAnnotator
            text={annotationText}
            candidates={candidates}
            hoveredCandidateId={hoveredId}
            ratedIds={ratedIds}
            onWordClick={handleWordClick}
            onWordHover={handleTextHover}
            onTextSelected={handleTextSelected}
            editingFragmentFor={interactionMode.type === 'editing' ? interactionMode.candidateId : null}
            disableHoverDimming={interactionMode.type === 'adding'}
          />
          {popoverState && interactionMode.type === 'editing' && (
            <TextSelectionPopover
              mode="edit"
              selectedText={popoverState.phrase}
              position={popoverState.position}
              onCancel={handlePopoverCancel}
              lemma={interactionMode.lemma}
              pos={interactionMode.pos}
              originalFragment={interactionMode.originalFragment}
              onSetBoundary={handleSetBoundary}
            />
          )}
          {popoverState && interactionMode.type === 'adding' && (
            <TextSelectionPopover
              mode="add"
              selectedText={popoverState.phrase}
              position={popoverState.position}
              onCancel={handlePopoverCancel}
              onAddWord={handleAddWord}
            />
          )}
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
