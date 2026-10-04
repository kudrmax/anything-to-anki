import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { api } from '@/api/client'
import type { CandidateStatus, CardPreview, FollowUpAction, GenerationKind, GenerationOverview, GenerationScope, SourceDetail, StoredCandidate } from '@/api/types'
import { autoPlayAudioPref, sortOrderPref, type SortOrder } from '@/lib/preferences'
import { isVpnError, isVpnErrorText } from '@/lib/aiErrors'
import { candidateAudioUrl } from '@/lib/candidateAudio'
import { mediaUrl } from '@/lib/text/meaning'
import { useToast } from '@/ui'
import { useAudioPlayer } from '@/lib/useAudioPlayer'
import { nextFocusId } from './nextFocus'

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

const hasCandidateVpnErrors = (candidates: StoredCandidate[]): boolean =>
  candidates.some(c => c.meaning?.status === 'failed' && isVpnErrorText(c.meaning.error))

export const audioUrlForCandidate = candidateAudioUrl

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
  const [generation, setGeneration] = useState<GenerationOverview | null>(null)
  const [vpnBlocked, setVpnBlocked] = useState(false)
  const [mediaMap, setMediaMap] = useState<Record<number, MediaRefs>>({})
  const [sortOrder, setSortOrderState] = useState<SortOrder>(() => sortOrderPref.read())
  const [editing, setEditing] = useState<Editing | null>(null)
  const [toast, showToast] = useToast()
  const [reportReasons, setReportReasons] = useState<string[]>([])
  useEffect(() => {
    api.getReportReasons().then(setReportReasons).catch(() => {})
  }, [])
  const player = useAudioPlayer()

  const setSortOrder = (order: SortOrder) => { sortOrderPref.write(order); setSortOrderState(order) }

  const fetchCandidates = useCallback(
    () => Promise.all([api.getCandidates(sourceId, sortOrder), fetchCards(sourceId)]),
    [sourceId, sortOrder],
  )

  const applyCandidates = useCallback(([cands, cards]: Awaited<ReturnType<typeof fetchCandidates>>) => {
    setCandidates(cands)
    if (hasCandidateVpnErrors(cands)) setVpnBlocked(true)
    setMediaMap(toMediaMap(cards))
  }, [])

  const loadCandidates = useCallback(async () => {
    applyCandidates(await fetchCandidates())
  }, [fetchCandidates, applyCandidates])

  const loadGeneration = useCallback(async () => {
    try {
      setGeneration(await api.getGenerationStatus(sourceId))
    } catch {
      // Панель генерации просто не покажет свежие числа до следующей попытки.
    }
  }, [sourceId])

  useEffect(() => {
    const load = async () => {
      try {
        const src = await api.getSource(sourceId, sortOrder)
        setSource(src)
        setCandidates(src.candidates)
        setCurrentId(prev => prev ?? firstPendingId(src.candidates))
        await Promise.all([fetchCards(sourceId).then(cards => setMediaMap(toMediaMap(cards))), loadGeneration()])
      } catch {
        setSource(null)
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [sourceId, sortOrder, loadGeneration])

  const inProgress = generation?.in_progress ?? false
  useEffect(() => {
    if (!inProgress) return
    const interval = setInterval(() => {
      void loadCandidates()
      void loadGeneration()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [inProgress, loadCandidates, loadGeneration])

  // Свежий список для mark(), чтобы не пересоздавать обработчик на каждое изменение.
  const candidatesRef = useRef<StoredCandidate[]>(candidates)
  useEffect(() => { candidatesRef.current = candidates }, [candidates])

  const { play, stop } = player
  const mark = useCallback(async (candidateId: number, status: CandidateStatus) => {
    stop()
    const markedIndex = candidatesRef.current.findIndex(c => c.id === candidateId)

    try {
      await api.markCandidate(candidateId, status)
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the decision')
      return
    }
    // Порядок задаёт backend: решённые фразы уходят вниз, известные слова пересортировывают
    // остальные. Новый порядок и смену фокуса применяем одним рендером, иначе карточка
    // сначала сворачивается на месте; следующую фразу выбираем уже по новому порядку.
    const refreshed = await fetchCandidates().catch(() => null)
    const fresh = refreshed?.[0] ?? candidatesRef.current.map(c => (c.id === candidateId ? { ...c, status } : c))
    if (refreshed) applyCandidates(refreshed)
    else setCandidates(fresh)

    if (status === 'pending') return
    const focusId = nextFocusId(fresh, candidateId, markedIndex)
    if (focusId === null) return
    setCurrentId(focusId)
    const focus = fresh.find(c => c.id === focusId)
    const nextUrl = focus && autoPlayAudioPref.read() ? audioUrlForCandidate(focus, sourceId) : null
    if (nextUrl) play(nextUrl)
  }, [sourceId, play, stop, showToast, fetchCandidates, applyCandidates])

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
      await loadGeneration()
    } catch (e) {
      if (options.vpnAware && isVpnError(e)) setVpnBlocked(true)
      else showToast(e instanceof Error ? e.message : fallback)
    }
  }

  const generationActions = {
    run: (kind: GenerationKind, scope: GenerationScope) =>
      runBatch(() => api.runGeneration(sourceId, kind, scope, sortOrder), 'Failed to start generation', { vpnAware: true }),
    cancel: (kind: GenerationKind) =>
      runBatch(() => api.cancelGeneration(sourceId, kind), 'Failed to cancel'),
    downloadVideo: () =>
      runBatch(() => api.downloadVideo(sourceId), 'Failed to download the video', { skipCandidates: true }),
  }

  const generateTTS = (candidateId: number) => withBusy(setGeneratingTTSIds, candidateId, async () => {
    try {
      await api.generateCandidateTTS(candidateId)
      await loadCandidates()
      await loadGeneration()
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

  /** true — граница сохранена; при ошибке показывает её и оставляет попап открытым. */
  const setBoundary = async (phrase: string): Promise<boolean> => {
    if (!editing) return false
    try {
      await api.updateCandidateFragment(editing.candidateId, phrase)
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the boundary')
      return false
    }
    cancelEditing()
    await loadCandidates()
    return true
  }

  /** true — слово добавлено; при ошибке показывает её и оставляет попап открытым. */
  const addWord = async (target: string, context: string): Promise<boolean> => {
    try {
      const result = await api.addManualCandidate(sourceId, target, context)
      window.getSelection()?.removeAllRanges()
      await loadCandidates()
      setCurrentId(result.id)
      return true
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to add the word')
      return false
    }
  }

  const polishAgain = async (candidateId: number) => {
    try {
      await api.polishPhraseAgain(candidateId)
      await loadCandidates()
      await loadGeneration()
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to polish the phrase')
    }
  }

  const setPolishReverted = async (candidateId: number, reverted: boolean) => {
    try {
      await api.setPolishReverted(candidateId, reverted)
      await loadCandidates()
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to switch the phrase')
    }
  }

  const report = async (candidateId: number, reasons: string[], comment: string): Promise<boolean> => {
    try {
      await api.reportCandidate(candidateId, reasons, comment)
      setCandidates(prev => prev.map(c => (c.id === candidateId ? { ...c, reported: true } : c)))
      showToast('Report saved')
      return true
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the report')
      return false
    }
  }

  const mediaFor = (candidate: StoredCandidate): MediaRefs => ({
    screenshotUrl: mediaUrl(sourceId, candidate.media?.screenshot_path) ?? mediaMap[candidate.id]?.screenshotUrl ?? null,
    audioUrl: mediaUrl(sourceId, candidate.media?.audio_path) ?? mediaMap[candidate.id]?.audioUrl ?? null,
  })

  const markedCount = candidates.filter(c => c.status !== 'pending').length
  const learnCount = candidates.filter(c => c.status === 'learn').length

  return {
    sourceId, source, candidates, loading, currentId, setCurrentId, sortOrder, setSortOrder,
    counts: { marked: markedCount, total: candidates.length, learn: learnCount, progress: candidates.length > 0 ? markedCount / candidates.length : 0 },
    generation, generationActions,
    mark, generate, replaceWithExample, generateTTS, regenerateMedia, polishAgain, setPolishReverted,
    busy: { generating: generatingIds, media: regeneratingMediaIds, tts: generatingTTSIds },
    vpnBlocked, dismissVpn: () => setVpnBlocked(false),
    editing, startEditing, cancelEditing, setBoundary, addWord,
    mediaFor, player, toast,
    reportReasons, report,
  }
}

export type Review = ReturnType<typeof useReview>
