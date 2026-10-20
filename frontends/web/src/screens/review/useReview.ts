import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { api } from '@/api/client'
import type { ButtonCommand, CardButton, DecisionButton, DocumentSelection, FollowUpAction, GenerationKind, GenerationOverview, GenerationScope, ImageSearchResult, ReportReason, ReviewDetail, SaveClozeRequest, SetScope, SourceDocument, StoredCandidate } from '@/api/types'
import { autoPlayAudioPref, sortOrderPref, type SortOrder } from '@/lib/preferences'
import { isVpnError, isVpnErrorText } from '@/lib/aiErrors'
import { messageOf } from '@/lib/apiError'
import { candidateAudioUrl } from '@/lib/candidateAudio'
import { mediaUrl } from '@/lib/text/meaning'
import { useToast } from '@/ui'
import { useAudioPlayer } from '@/lib/useAudioPlayer'
import { initialFocusId } from './initialFocus'
import { keepLayout } from './keptLayout'
import { focusAfterPress } from './nextFocus'
import type { SelectedText } from './SourceText'

const POLL_INTERVAL_MS = 3000

interface MediaRefs {
  screenshotUrl: string | null
  audioUrl: string | null
  meaningImageUrl: string | null
}

export interface Editing {
  candidateId: number
  /** Источник фразы: новая граница выделяется в его тексте. */
  sourceId: number
  lemma: string
  pos: string
  originalFragment: string
}

const hasCandidateVpnErrors = (candidates: StoredCandidate[]): boolean =>
  candidates.some(c => c.meaning?.status === 'failed' && isVpnErrorText(c.meaning.error))

export const audioUrlForCandidate = candidateAudioUrl

export function useReview(scope: SetScope, requestedId: number | null = null) {
  const [detail, setDetail] = useState<ReviewDetail | null>(null)
  const [documents, setDocuments] = useState<SourceDocument[]>([])
  const [candidates, setCandidates] = useState<StoredCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [currentId, setCurrentId] = useState<number | null>(null)
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [regeneratingMediaIds, setRegeneratingMediaIds] = useState<Set<number>>(new Set())
  const [generatingTTSIds, setGeneratingTTSIds] = useState<Set<number>>(new Set())
  const [applyingImageIds, setApplyingImageIds] = useState<Set<number>>(new Set())
  const [generation, setGeneration] = useState<GenerationOverview | null>(null)
  const [vpnBlocked, setVpnBlocked] = useState(false)
  const [sortOrder, setSortOrderState] = useState<SortOrder>(() => sortOrderPref.read())
  const [editing, setEditing] = useState<Editing | null>(null)
  const [toast, showToast] = useToast()
  const [reportReasons, setReportReasons] = useState<ReportReason[]>([])
  useEffect(() => {
    api.getReportReasons().then(setReportReasons).catch(() => {})
  }, [])
  const player = useAudioPlayer()

  const setSortOrder = (order: SortOrder) => { sortOrderPref.write(order); setSortOrderState(order) }

  // Набор вместе с кандидатами: разделы и счётчик считает backend по всем карточкам.
  const fetchReview = useCallback(
    () => api.getReview(scope, sortOrder),
    [scope, sortOrder],
  )

  // Перечитанные карточки встают в порядок, снятый при загрузке; перегруппирует их только загрузка списка.
  const applyReview = useCallback((review: ReviewDetail) => {
    setDetail(review)
    setCandidates(prev => keepLayout(prev, review.candidates))
    if (hasCandidateVpnErrors(review.candidates)) setVpnBlocked(true)
  }, [])

  const loadDocuments = useCallback(async () => {
    // Подсветки в текстах следуют за кандидатами: после правок их надо перечитать.
    setDocuments(await api.getReviewDocuments(scope).catch(() => []))
  }, [scope])

  const loadCandidates = useCallback(async () => {
    applyReview(await fetchReview())
    await loadDocuments()
  }, [fetchReview, applyReview, loadDocuments])

  const loadGeneration = useCallback(async () => {
    try {
      setGeneration(await api.getReviewGeneration(scope))
    } catch {
      // Панель генерации просто не покажет свежие числа до следующей попытки.
    }
  }, [scope])

  useEffect(() => {
    const load = async () => {
      try {
        const review = await api.getReview(scope, sortOrder)
        setDetail(review)
        setCandidates(review.candidates)
        await loadDocuments()
        setCurrentId(prev => prev ?? initialFocusId(review.candidates, requestedId))
        await loadGeneration()
      } catch {
        setDetail(null)
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [scope, sortOrder, loadGeneration, loadDocuments, requestedId])

  const inProgress = generation?.in_progress ?? false
  useEffect(() => {
    if (!inProgress) return
    const interval = setInterval(() => {
      void loadCandidates()
      void loadGeneration()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [inProgress, loadCandidates, loadGeneration])

  // Пока источник набора занят (Rebuild, Refresh), карточки перечитываются; последнее чтение — уже после операции.
  const busySet = detail?.busy ?? false
  useEffect(() => {
    if (!busySet) return
    const interval = setInterval(() => void loadCandidates(), POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [busySet, loadCandidates])

  // Свежий список для settle(), чтобы не пересоздавать обработчик на каждое изменение.
  const candidatesRef = useRef<StoredCandidate[]>(candidates)
  useEffect(() => { candidatesRef.current = candidates }, [candidates])

  const { play, stop } = player

  // Показанная карточка сама играет своё аудио: при открытии, после решения, при листании.
  useEffect(() => {
    if (currentId === null || !autoPlayAudioPref.read()) return
    const shown = candidatesRef.current.find(c => c.phrase_id === currentId)
    const url = shown ? audioUrlForCandidate(shown) : null
    if (url) play(url)
    else stop()
  }, [currentId, play, stop])

  /**
   * После решения по фразе: свежие данные карточек, а нажатая остаётся на месте до перезагрузки списка.
   * Фокус уходит к следующей открытой, когда нажатая стала разобранной. Данные и фокус — одним рендером.
   */
  const settle = useCallback(async (candidateId: number, saved?: StoredCandidate) => {
    const marked = candidatesRef.current.find(c => c.phrase_id === candidateId)
    const markedSection = marked?.section ?? null
    const refreshed = await fetchReview().catch(() => null)
    const fresh = keepLayout(
      candidatesRef.current,
      refreshed?.candidates ?? candidatesRef.current.map(c => (saved && c.phrase_id === candidateId ? saved : c)),
    )
    if (refreshed) {
      setDetail(refreshed)
      if (hasCandidateVpnErrors(refreshed.candidates)) setVpnBlocked(true)
    }
    setCandidates(fresh)

    const focusId = focusAfterPress(fresh, candidateId, marked?.is_done ?? false, sortOrder === 'chronological' ? null : markedSection)
    if (focusId === null) return
    setCurrentId(focusId)
  }, [sortOrder, fetchReview])

  /** Нажатие кнопки, которую backend сказал слать; ответ — карточка после него. */
  const mark = useCallback(async (candidateId: number, button: DecisionButton) => {
    stop()
    let decided: StoredCandidate
    try {
      decided = await api.decidePhrase(candidateId, button)
    } catch (e) {
      showToast(messageOf(e))
      return
    }
    await settle(candidateId, decided)
  }, [stop, showToast, settle])

  const [clozeEditingId, setClozeEditingId] = useState<number | null>(null)
  // Разметка cloze относится к одной карточке: при переходе на другую она закрывается.
  useEffect(() => { setClozeEditingId(null) }, [currentId])
  const startCloze = useCallback((candidateId: number) => {
    window.getSelection()?.removeAllRanges()
    setClozeEditingId(candidateId)
  }, [])
  const cancelCloze = useCallback(() => setClozeEditingId(null), [])

  /** Кнопка карточки делает то, что сказал backend: открывает разметку cloze или шлёт решение. */
  const press = useCallback(async (candidateId: number, button: CardButton) => {
    if (button.command === null) return
    const run: Record<ButtonCommand, () => Promise<void>> = {
      edit_cloze: async () => startCloze(candidateId),
      decide: async () => {
        setClozeEditingId(null)
        await mark(candidateId, button.button)
      },
    }
    await run[button.command]()
  }, [startCloze, mark])

  /** true — разметка сохранена (фокус уходит, если карточка стала разобранной); при ошибке показывает её. */
  const saveCloze = useCallback(async (candidateId: number, request: SaveClozeRequest): Promise<boolean> => {
    stop()
    let saved: StoredCandidate
    try {
      saved = await api.saveCloze(candidateId, request)
    } catch (e) {
      showToast(messageOf(e))
      return false
    }
    setClozeEditingId(null)
    await settle(candidateId, saved)
    return true
  }, [stop, showToast, settle])

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
        // Карточку с новым значением и тем, что она теперь предлагает, отдаёт backend.
        await loadCandidates()
        showToast(`Tokens used: ${res.tokens_used}`)
      } catch (e) {
        if (isVpnError(e)) setVpnBlocked(true)
        else showToast(e instanceof Error ? e.message : action ? 'Follow-up failed' : 'Generation failed')
      }
    }), [showToast, loadCandidates])

  const replaceWithExample = useCallback(async (candidateId: number, exampleText: string) => {
    try {
      const newCandidate = await api.replaceWithExample(candidateId, exampleText)
      // Пример — новая фраза слова: он встаёт на место заменённой карточки, которая больше не показана.
      setCandidates(prev => prev.map(c => (c.phrase_id === candidateId ? newCandidate : c)))
      setCurrentId(newCandidate.phrase_id)
      showToast('Phrase replaced — generating meaning...')
      await loadGeneration()
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Replace failed')
    }
  }, [loadGeneration, showToast])

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
    run: (kind: GenerationKind, cards: GenerationScope) =>
      runBatch(() => api.runReviewGeneration(scope, kind, cards, sortOrder), 'Failed to start generation', { vpnAware: true }),
    cancel: (kind: GenerationKind) =>
      runBatch(() => api.cancelReviewGeneration(scope, kind), 'Failed to cancel'),
    downloadVideo: () =>
      runBatch(() => api.downloadReviewVideos(scope), 'Failed to download the video', { skipCandidates: true }),
  }

  const generateTTS = (candidateId: number) => withBusy(setGeneratingTTSIds, candidateId, async () => {
    try {
      await api.generatePhraseTTS(candidateId)
      await loadCandidates()
      await loadGeneration()
      showToast('TTS enqueued')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'TTS failed')
    }
  })

  const regenerateMedia = (candidateId: number) => withBusy(setRegeneratingMediaIds, candidateId, async () => {
    try {
      await api.regeneratePhraseMedia(candidateId)
      await loadCandidates()
      showToast('Media regenerated')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Regeneration failed')
    }
  })

  const findImages = async (candidateId: number, query?: string): Promise<ImageSearchResult | null> => {
    try {
      return await api.searchTargetImages(wordOf(candidatesRef.current, candidateId), query)
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Picture search failed')
      return null
    }
  }

  const applyImage = (candidateId: number, url: string) => withBusy(setApplyingImageIds, candidateId, async () => {
    try {
      await api.applyTargetImage(wordOf(candidatesRef.current, candidateId), url)
      await loadCandidates()
      showToast('Picture added')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to add the picture')
    }
  })

  const pasteImage = (candidateId: number, picture: Blob) => withBusy(setApplyingImageIds, candidateId, async () => {
    try {
      await api.pasteTargetImage(wordOf(candidatesRef.current, candidateId), picture)
      await loadCandidates()
      showToast('Picture pasted')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to paste the picture')
    }
  })

  const startEditing = (candidateId: number) => {
    const candidate = candidates.find(c => c.phrase_id === candidateId)
    if (!candidate) return
    setEditing({ candidateId, sourceId: candidate.source.id, lemma: candidate.lemma, pos: candidate.pos, originalFragment: candidate.source_phrase.text })
  }

  const cancelEditing = useCallback(() => {
    setEditing(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  /** true — граница сохранена; при ошибке показывает её и оставляет попап открытым. */
  const setBoundary = async (selection: DocumentSelection): Promise<boolean> => {
    if (!editing) return false
    try {
      await api.setPhraseBoundary(editing.candidateId, selection)
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the boundary')
      return false
    }
    cancelEditing()
    await loadCandidates()
    return true
  }

  /** true — слово добавлено; при ошибке показывает её и оставляет попап открытым. */
  const addWord = async (targetWords: number[], selected: SelectedText): Promise<boolean> => {
    try {
      const result = await api.addManualCandidate(selected.sourceId, targetWords, selected.selection)
      window.getSelection()?.removeAllRanges()
      await loadCandidates()
      setCurrentId(result.phrase_id)
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

  /** true — фраза сохранена; при ошибке показывает её и оставляет правку открытой. */
  const editPhrase = async (candidateId: number, phrase: string): Promise<boolean> => {
    try {
      await api.editPhrase(candidateId, phrase)
      await loadCandidates()
      return true
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the phrase')
      return false
    }
  }

  /** unknownWords — слова фразы карточки, которые пользователь не знает: карточки с ними уходят из Ready. */
  const report = async (candidateId: number, reasons: string[], comment: string, unknownWords: number[] = []): Promise<boolean> => {
    try {
      await api.reportCandidate(candidateId, reasons, comment, unknownWords)
      if (unknownWords.length > 0) await loadCandidates()
      else setCandidates(prev => prev.map(c => (c.phrase_id === candidateId ? { ...c, reported: true } : c)))
      showToast('Report saved')
      return true
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the report')
      return false
    }
  }

  // Медиа лежат у источника карточки, а не у экрана: в наборе у карточек разные источники.
  const mediaFor = (candidate: StoredCandidate): MediaRefs => ({
    screenshotUrl: mediaUrl(candidate.source.id, candidate.media?.screenshot_path),
    audioUrl: mediaUrl(candidate.source.id, candidate.media?.audio_path),
    meaningImageUrl: mediaUrl(candidate.source.id, candidate.meaning_image_path),
  })

  // Счётчик — Reviewed / (Reviewed + открытые Ready); числа считает backend.
  const learnCount = detail?.learn_count ?? 0
  const progressTotal = detail?.progress.total ?? 0
  const progressReviewed = detail?.progress.decided ?? 0

  return {
    scope, detail, documents, candidates, loading, currentId, setCurrentId, sortOrder, setSortOrder,
    counts: { reviewed: progressReviewed, total: progressTotal, learn: learnCount, progress: progressTotal > 0 ? progressReviewed / progressTotal : 0 },
    generation, generationActions,
    press, generate, replaceWithExample,
    clozeEditingId, clozeEditing: clozeEditingId !== null, startCloze, cancelCloze, saveCloze, generateTTS, regenerateMedia, findImages, applyImage, pasteImage, polishAgain, setPolishReverted, editPhrase,
    busy: { generating: generatingIds, media: regeneratingMediaIds, tts: generatingTTSIds, image: applyingImageIds },
    vpnBlocked, dismissVpn: () => setVpnBlocked(false),
    editing, startEditing, cancelEditing, setBoundary, addWord,
    mediaFor, player, toast,
    reportReasons, report,
  }
}

export type Review = ReturnType<typeof useReview>

/** Слово карточки: картинка — свойство слова, а не фразы. */
function wordOf(candidates: StoredCandidate[], candidateId: number): number {
  const wordId = candidates.find(c => c.phrase_id === candidateId)?.word_id
  if (wordId == null) throw new Error('The card is not in the list')
  return wordId
}
