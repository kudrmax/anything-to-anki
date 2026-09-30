import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { api } from '@/api/client'
import type { CandidateStatus, CardPreview, FollowUpAction, QueueStatus, QueueSummary, SourceDetail, StoredCandidate } from '@/api/types'
import { autoPlayAudioPref, sortOrderPref, type SortOrder } from '@/lib/preferences'
import { mediaUrl } from '@/lib/text/meaning'
import { useToast } from '@/ui'
import { useAudioPlayer } from './useAudioPlayer'

const VPN_ERROR_MARKER = 'Blocked country'
const POLL_INTERVAL_MS = 3000

interface MediaRefs {
  screenshotUrl: string | null
  audioUrl: string | null
}

export interface Editing {
  candidateId: number
  lemma: string
  pos: string
  originalFragment: string
}

const isVpnError = (e: unknown): boolean => e instanceof Error && e.message.includes(VPN_ERROR_MARKER)

const hasCandidateVpnErrors = (candidates: StoredCandidate[]): boolean =>
  candidates.some(c => c.meaning?.status === 'failed' && c.meaning.error?.includes(VPN_ERROR_MARKER))

/** Аудио контекста из видео, иначе произношение US. */
export function audioUrlForCandidate(candidate: StoredCandidate, sourceId: number): string | null {
  return mediaUrl(sourceId, candidate.media?.audio_path) ?? mediaUrl(sourceId, candidate.pronunciation?.us_audio_path)
}

const inflight = (status: QueueStatus | undefined): number => (status?.queued ?? 0) + (status?.running ?? 0)

const toMediaMap = (cards: CardPreview[]): Record<number, MediaRefs> => {
  const map: Record<number, MediaRefs> = {}
  for (const card of cards) map[card.candidate_id] = { screenshotUrl: card.screenshot_url, audioUrl: card.audio_url }
  return map
}

const fetchCards = (sourceId: number): Promise<CardPreview[]> =>
  api.getExportCards(sourceId).then(d => d.sections.flatMap(s => s.cards)).catch(() => [] as CardPreview[])

const firstPendingId = (candidates: StoredCandidate[]): number | null =>
  (candidates.find(c => c.status === 'pending') ?? candidates[0])?.id ?? null

export function useReview(sourceId: number) {
  const [source, setSource] = useState<SourceDetail | null>(null)
  const [candidates, setCandidates] = useState<StoredCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [currentId, setCurrentId] = useState<number | null>(null)
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [regeneratingMediaIds, setRegeneratingMediaIds] = useState<Set<number>>(new Set())
  const [generatingTTSIds, setGeneratingTTSIds] = useState<Set<number>>(new Set())
  const [queueSummary, setQueueSummary] = useState<QueueSummary | null>(null)
  const [vpnBlocked, setVpnBlocked] = useState(false)
  const [downloadingVideo, setDownloadingVideo] = useState(false)
  const [mediaMap, setMediaMap] = useState<Record<number, MediaRefs>>({})
  const [sortOrder, setSortOrderState] = useState<SortOrder>(() => sortOrderPref.read())
  const [editing, setEditing] = useState<Editing | null>(null)
  const [toast, showToast] = useToast()
  const player = useAudioPlayer()

  const setSortOrder = (order: SortOrder) => { sortOrderPref.write(order); setSortOrderState(order) }

  const loadCandidates = useCallback(async () => {
    const [cands, cards] = await Promise.all([api.getCandidates(sourceId, sortOrder), fetchCards(sourceId)])
    setCandidates(cands)
    if (hasCandidateVpnErrors(cands)) setVpnBlocked(true)
    setMediaMap(toMediaMap(cards))
  }, [sourceId, sortOrder])

  const loadQueueSummary = useCallback(async () => {
    try {
      setQueueSummary(await api.getQueueSummary(sourceId))
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
        setCurrentId(prev => prev ?? firstPendingId(src.candidates))
        await Promise.all([fetchCards(sourceId).then(cards => setMediaMap(toMediaMap(cards))), loadQueueSummary()])
      } catch {
        setSource(null)
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [sourceId, sortOrder, loadQueueSummary])

  // Polling while there are inflight jobs
  const anyInflight = inflight(queueSummary?.meaning) + inflight(queueSummary?.media)
    + inflight(queueSummary?.pronunciation) + inflight(queueSummary?.tts) > 0
  useEffect(() => {
    if (!anyInflight) return
    const interval = setInterval(() => {
      void loadCandidates()
      void loadQueueSummary()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [anyInflight, loadCandidates, loadQueueSummary])

  // Свежий список для mark(), чтобы не пересоздавать обработчик на каждое изменение.
  const candidatesRef = useRef<StoredCandidate[]>(candidates)
  useEffect(() => { candidatesRef.current = candidates }, [candidates])

  const { play, stop } = player
  const mark = useCallback(async (candidateId: number, status: CandidateStatus) => {
    stop()

    // Capture the next pending candidate BEFORE marking — once we mark,
    // this one is removed from the pending list and 'next' shifts.
    const pending = candidatesRef.current.filter(c => c.status === 'pending')
    const idx = pending.findIndex(c => c.id === candidateId)
    const nextPending = idx >= 0 && idx + 1 < pending.length ? pending[idx + 1] : null
    const nextUrl = nextPending && autoPlayAudioPref.read() ? audioUrlForCandidate(nextPending, sourceId) : null

    await api.markCandidate(candidateId, status)
    setCandidates(prev => prev.map(c => (c.id === candidateId ? { ...c, status } : c)))

    if (status !== 'pending') {
      const focus = nextPending ?? pending.find(c => c.id !== candidateId) ?? null
      if (focus) setCurrentId(focus.id)
    }
    if (nextUrl) play(nextUrl)
  }, [sourceId, play, stop])

  const withBusy = async (setIds: Dispatch<SetStateAction<Set<number>>>, id: number, run: () => Promise<void>) => {
    setIds(prev => new Set(prev).add(id))
    try {
      await run()
    } finally {
      setIds(prev => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const generate = useCallback((candidateId: number, action?: FollowUpAction, text?: string) =>
    withBusy(setGeneratingIds, candidateId, async () => {
      try {
        const res = await api.generateMeaning(candidateId, action, text)
        setCandidates(prev => prev.map(c => (c.id === candidateId ? {
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
        } : c)))
        showToast(`Tokens used: ${res.tokens_used}`)
      } catch (e) {
        if (isVpnError(e)) setVpnBlocked(true)
        else showToast(e instanceof Error ? e.message : action ? 'Follow-up failed' : 'Generation failed')
      }
    }), [showToast])

  const replaceWithExample = useCallback(async (candidateId: number, exampleText: string) => {
    try {
      const newCandidate = await api.replaceWithExample(candidateId, exampleText)
      setCandidates(prev => [...prev.map(c => (c.id === candidateId ? { ...c, status: 'skip' as const } : c)), newCandidate])
      setCurrentId(newCandidate.id)
      void generate(newCandidate.id)
      showToast('Phrase replaced — generating meaning...')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Replace failed')
    }
  }, [generate, showToast])

  const runBatch = async (call: () => Promise<unknown>, fallback: string, options: { vpnAware?: boolean; skipCandidates?: boolean } = {}) => {
    try {
      await call()
      if (!options.skipCandidates) await loadCandidates()
      await loadQueueSummary()
    } catch (e) {
      if (options.vpnAware && isVpnError(e)) setVpnBlocked(true)
      else showToast(e instanceof Error ? e.message : fallback)
    }
  }

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const downloadVideo = async () => {
    setDownloadingVideo(true)
    try {
      await api.downloadVideo(sourceId)
      pollRef.current = setInterval(() => {
        void api.getSource(sourceId, sortOrder).then(updated => {
          setSource(updated)
          if (updated.video_downloaded) {
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null
            setDownloadingVideo(false)
          }
        }).catch(() => undefined)
      }, POLL_INTERVAL_MS)
    } catch {
      setDownloadingVideo(false)
    }
  }

  const batch = {
    generateMeanings: () => runBatch(() => api.enqueueMeaningGeneration(sourceId, sortOrder), 'Failed to enqueue meanings', { vpnAware: true }),
    cancelMeanings: () => runBatch(() => api.cancelMeaningQueue(sourceId), 'Failed to cancel'),
    retryMeanings: () => runBatch(() => api.retryFailedMeanings(sourceId), 'Failed to retry', { vpnAware: true }),
    generateMedia: () => runBatch(() => api.enqueueMediaGeneration(sourceId, sortOrder), 'Failed to enqueue media'),
    cancelMedia: () => runBatch(() => api.cancelMediaQueue(sourceId), 'Failed to cancel'),
    retryMedia: () => runBatch(() => api.retryFailedMedia(sourceId), 'Failed to retry'),
    downloadVideo,
    downloadPronunciation: () => runBatch(() => api.enqueuePronunciationDownload(sourceId), 'Failed to enqueue pronunciation'),
    cancelPronunciation: () => runBatch(() => api.cancelPronunciationQueue(sourceId), 'Cancel failed'),
    retryPronunciation: () => runBatch(() => api.retryFailedPronunciation(sourceId), 'Retry failed'),
    generateTTS: () => runBatch(() => api.enqueueTTSGeneration(sourceId), 'Failed to enqueue TTS'),
    cancelTTS: () => runBatch(() => api.cancelTTSQueue(sourceId), 'Failed to cancel', { skipCandidates: true }),
    retryTTS: () => runBatch(() => api.retryFailedTTS(sourceId), 'Failed to retry'),
  }

  const generateTTS = (candidateId: number) => withBusy(setGeneratingTTSIds, candidateId, async () => {
    try {
      await api.generateCandidateTTS(candidateId)
      await loadCandidates()
      await loadQueueSummary()
      showToast('TTS enqueued')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'TTS failed')
    }
  })

  const regenerateMedia = (candidateId: number) => withBusy(setRegeneratingMediaIds, candidateId, async () => {
    try {
      await api.regenerateCandidateMedia(candidateId)
      await loadCandidates()
      showToast('Media regenerated')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Regeneration failed')
    }
  })

  const startEditing = (candidateId: number) => {
    const candidate = candidates.find(c => c.id === candidateId)
    if (!candidate) return
    setEditing({ candidateId, lemma: candidate.lemma, pos: candidate.pos, originalFragment: candidate.context_fragment })
  }

  const cancelEditing = useCallback(() => {
    setEditing(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  const setBoundary = async (phrase: string) => {
    if (!editing) return
    await api.updateCandidateFragment(editing.candidateId, phrase)
    setCandidates(prev => prev.map(c => (c.id === editing.candidateId ? { ...c, context_fragment: phrase } : c)))
    cancelEditing()
  }

  const addWord = async (target: string, context: string) => {
    const result = await api.addManualCandidate(sourceId, target, context)
    window.getSelection()?.removeAllRanges()
    await loadCandidates()
    setCurrentId(result.id)
  }

  // Auto-save source status only when the derived status actually changes,
  // not on every candidates re-fetch (which happens during polling).
  const autoSaveRef = useRef(false)
  const lastSavedStatusRef = useRef<string | null>(null)
  useEffect(() => {
    if (loading) return
    const anyPending = candidates.some(c => c.status === 'pending')
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

  const mediaFor = (candidate: StoredCandidate): MediaRefs => ({
    screenshotUrl: mediaUrl(sourceId, candidate.media?.screenshot_path) ?? mediaMap[candidate.id]?.screenshotUrl ?? null,
    audioUrl: mediaUrl(sourceId, candidate.media?.audio_path) ?? mediaMap[candidate.id]?.audioUrl ?? null,
  })

  const markedCount = candidates.filter(c => c.status !== 'pending').length
  const learnCount = candidates.filter(c => c.status === 'learn').length

  return {
    sourceId, source, candidates, loading, currentId, setCurrentId, sortOrder, setSortOrder,
    counts: { marked: markedCount, total: candidates.length, learn: learnCount, progress: candidates.length > 0 ? markedCount / candidates.length : 0 },
    queue: {
      meaning: { inflight: inflight(queueSummary?.meaning), failed: queueSummary?.meaning?.failed ?? 0 },
      media: { inflight: inflight(queueSummary?.media), failed: queueSummary?.media?.failed ?? 0 },
      pronunciation: { inflight: inflight(queueSummary?.pronunciation), failed: queueSummary?.pronunciation?.failed ?? 0 },
      tts: { inflight: inflight(queueSummary?.tts), failed: queueSummary?.tts?.failed ?? 0 },
      anyInflight,
    },
    batch, downloadingVideo,
    mark, generate, replaceWithExample, generateTTS, regenerateMedia,
    busy: { generating: generatingIds, media: regeneratingMediaIds, tts: generatingTTSIds },
    vpnBlocked, dismissVpn: () => setVpnBlocked(false),
    editing, startEditing, cancelEditing, setBoundary, addWord,
    mediaFor, player, toast,
  }
}

export type Review = ReturnType<typeof useReview>
