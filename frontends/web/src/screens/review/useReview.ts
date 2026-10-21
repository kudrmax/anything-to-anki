import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import { api } from '@/api/client'
import type { ButtonCommand, CandidateSection, CardButton, DecisionButton, DocumentSelection, FollowUpAction, GenerationKind, GenerationScope, ImageSearchResult, ReportReason, ReviewUpdate, SaveClozeRequest, SetScope, StoredCandidate } from '@/api/types'
import { autoPlayAudioPref, sortOrderPref, type SortOrder } from '@/lib/preferences'
import { messageOf } from '@/lib/apiError'
import { candidateAudioUrl } from '@/lib/candidateAudio'
import { mediaUrl } from '@/lib/text/meaning'
import { useToast } from '@/ui'
import { useAudioPlayer } from '@/lib/useAudioPlayer'
import type { SelectedText } from './SourceText'
import { useReviewWindow } from './useReviewWindow'

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

export const audioUrlForCandidate = candidateAudioUrl

export function useReview(scope: SetScope, requestedId: number | null = null) {
  const [sortOrder, setSortOrderState] = useState<SortOrder>(() => sortOrderPref.read())
  const view = useReviewWindow(scope, sortOrder, requestedId)
  const { state, mutate, cardOf, loadGeneration } = view
  const currentId = state.currentId
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [regeneratingMediaIds, setRegeneratingMediaIds] = useState<Set<number>>(new Set())
  const [generatingTTSIds, setGeneratingTTSIds] = useState<Set<number>>(new Set())
  const [applyingImageIds, setApplyingImageIds] = useState<Set<number>>(new Set())
  const [editing, setEditing] = useState<Editing | null>(null)
  const [toast, showToast] = useToast()
  const [reportReasons, setReportReasons] = useState<ReportReason[]>([])
  useEffect(() => {
    api.getReportReasons().then(setReportReasons).catch(() => {})
  }, [])
  const player = useAudioPlayer()

  const setSortOrder = (order: SortOrder) => { sortOrderPref.write(order); setSortOrderState(order) }

  const { play, stop } = player

  // Показанная карточка сама играет своё аудио: при открытии, после решения, при листании.
  useEffect(() => {
    if (currentId === null || !autoPlayAudioPref.read()) return
    const shown = cardOf(currentId)
    const url = shown ? audioUrlForCandidate(shown) : null
    if (url) play(url)
    else stop()
  }, [currentId, cardOf, play, stop])

  /** К карточке по клику: дальняя приходит с окном вокруг неё. */
  const { goTo: goToCard } = view
  const goTo = useCallback(async (candidateId: number) => {
    try {
      await goToCard(candidateId)
    } catch (e) {
      showToast(messageOf(e))
    }
  }, [goToCard, showToast])

  /** Нажатие кнопки, которую backend сказал слать; ответ — изменения и следующая карточка. */
  const mark = useCallback(async (candidateId: number, button: DecisionButton) => {
    stop()
    try {
      await mutate(ctx => api.decidePhrase(ctx, candidateId, button))
    } catch (e) {
      showToast(messageOf(e))
    }
  }, [stop, showToast, mutate])

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
    try {
      await mutate(ctx => api.saveCloze(ctx, candidateId, request))
    } catch (e) {
      showToast(messageOf(e))
      return false
    }
    setClozeEditingId(null)
    return true
  }, [stop, showToast, mutate])

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
        // Задача в очереди: карточка показывает её статус, опрос подхватывает результат.
        await mutate(ctx => api.generateMeaning(ctx, candidateId, action, text))
        await loadGeneration()
      } catch (e) {
        showToast(e instanceof Error ? e.message : action ? 'Follow-up failed' : 'Generation failed')
      }
    }), [showToast, mutate, loadGeneration])

  const replaceWithExample = useCallback(async (candidateId: number, exampleText: string) => {
    try {
      // Пример — новая фраза слова: он встаёт на место заменённой карточки и становится текущим.
      await mutate(ctx => api.replaceWithExample(ctx, candidateId, exampleText))
      showToast('Phrase replaced — generating meaning...')
      await loadGeneration()
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Replace failed')
    }
  }, [mutate, loadGeneration, showToast])

  const runBatch = async (change: () => Promise<ReviewUpdate>, fallback: string) => {
    try {
      await change()
      await loadGeneration()
    } catch (e) {
      showToast(e instanceof Error ? e.message : fallback)
    }
  }

  const generationActions = {
    run: (kind: GenerationKind, cards: GenerationScope) =>
      runBatch(() => mutate(ctx => api.runReviewGeneration(ctx, scope, kind, cards, sortOrder)), 'Failed to start generation'),
    cancel: (kind: GenerationKind) =>
      runBatch(() => mutate(ctx => api.cancelReviewGeneration(ctx, scope, kind)), 'Failed to cancel'),
    downloadVideo: () =>
      runBatch(() => mutate(ctx => api.downloadReviewVideos(ctx, scope)), 'Failed to download the video'),
  }

  const generateTTS = (candidateId: number) => withBusy(setGeneratingTTSIds, candidateId, async () => {
    try {
      await mutate(ctx => api.generatePhraseTTS(ctx, candidateId))
      await loadGeneration()
      showToast('TTS enqueued')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'TTS failed')
    }
  })

  const regenerateMedia = (candidateId: number) => withBusy(setRegeneratingMediaIds, candidateId, async () => {
    try {
      await mutate(ctx => api.regeneratePhraseMedia(ctx, candidateId))
      showToast('Media regenerated')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Regeneration failed')
    }
  })

  /** Слово карточки: картинка — свойство слова, а не фразы. */
  const wordOf = (candidateId: number): number => {
    const wordId = cardOf(candidateId)?.word_id
    if (wordId == null) throw new Error('The card is not in the list')
    return wordId
  }

  const findImages = async (candidateId: number, query?: string): Promise<ImageSearchResult | null> => {
    try {
      return await api.searchTargetImages(wordOf(candidateId), query)
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Picture search failed')
      return null
    }
  }

  const applyImage = (candidateId: number, url: string) => withBusy(setApplyingImageIds, candidateId, async () => {
    try {
      const wordId = wordOf(candidateId)
      await mutate(ctx => api.applyTargetImage(ctx, wordId, url))
      showToast('Picture added')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to add the picture')
    }
  })

  const pasteImage = (candidateId: number, picture: Blob) => withBusy(setApplyingImageIds, candidateId, async () => {
    try {
      const wordId = wordOf(candidateId)
      await mutate(ctx => api.pasteTargetImage(ctx, wordId, picture))
      showToast('Picture pasted')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to paste the picture')
    }
  })

  const startEditing = (candidateId: number) => {
    const candidate = cardOf(candidateId)
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
    const { candidateId } = editing
    try {
      await mutate(ctx => api.setPhraseBoundary(ctx, candidateId, selection))
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the boundary')
      return false
    }
    cancelEditing()
    return true
  }

  /** true — слово добавлено; при ошибке показывает её и оставляет попап открытым. */
  const addWord = async (targetWords: number[], selected: SelectedText): Promise<boolean> => {
    try {
      await mutate(ctx => api.addManualCandidate(ctx, selected.sourceId, targetWords, selected.selection))
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to add the word')
      return false
    }
    window.getSelection()?.removeAllRanges()
    return true
  }

  const polishAgain = async (candidateId: number) => {
    try {
      await mutate(ctx => api.polishPhraseAgain(ctx, candidateId))
      await loadGeneration()
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to polish the phrase')
    }
  }

  const setPolishReverted = async (candidateId: number, reverted: boolean) => {
    try {
      await mutate(ctx => api.setPolishReverted(ctx, candidateId, reverted))
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to switch the phrase')
    }
  }

  /** true — фраза сохранена; при ошибке показывает её и оставляет правку открытой. */
  const editPhrase = async (candidateId: number, phrase: string): Promise<boolean> => {
    try {
      await mutate(ctx => api.editPhrase(ctx, candidateId, phrase))
      return true
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the phrase')
      return false
    }
  }

  /** unknownWords — слова фразы карточки, которые пользователь не знает: карточки с ними уходят из Ready. */
  const report = async (candidateId: number, reasons: string[], comment: string, unknownWords: number[] = []): Promise<boolean> => {
    try {
      await mutate(ctx => api.reportCandidate(ctx, candidateId, reasons, comment, unknownWords))
      showToast('Report saved')
      return true
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save the report')
      return false
    }
  }

  const toggleSection = async (section: CandidateSection, isOpen: boolean) => {
    try {
      await view.toggleSection(section, isOpen)
    } catch (e) {
      showToast(messageOf(e))
    }
  }

  // Медиа лежат у источника карточки, а не у экрана: в наборе у карточек разные источники.
  const mediaFor = (candidate: StoredCandidate): MediaRefs => ({
    screenshotUrl: mediaUrl(candidate.source.id, candidate.media?.screenshot_path),
    audioUrl: mediaUrl(candidate.source.id, candidate.media?.audio_path),
    meaningImageUrl: mediaUrl(candidate.source.id, candidate.meaning_image_path),
  })

  // Счётчик — Reviewed / (Reviewed + открытые Ready); числа считает backend.
  const { header } = state
  const learnCount = header?.learn_count ?? 0
  const progressTotal = header?.progress.total ?? 0
  const progressReviewed = header?.progress.decided ?? 0

  return {
    scope, header, state, loading: view.loading, gone: view.gone,
    text: view.text, hasSourceText: view.hasSourceText, loadText: view.loadText, ensureBlock: view.ensureBlock,
    current: view.current, currentId, position: view.position, canPrev: view.canPrev, canNext: view.canNext,
    goTo, step: view.step, loadRows: view.loadRows, toggleSection,
    sortOrder, setSortOrder,
    counts: { reviewed: progressReviewed, total: progressTotal, learn: learnCount, progress: progressTotal > 0 ? progressReviewed / progressTotal : 0 },
    generation: view.generation, generationActions,
    press, generate, replaceWithExample,
    clozeEditingId, clozeEditing: clozeEditingId !== null, startCloze, cancelCloze, saveCloze, generateTTS, regenerateMedia, findImages, applyImage, pasteImage, polishAgain, setPolishReverted, editPhrase,
    busy: { generating: generatingIds, media: regeneratingMediaIds, tts: generatingTTSIds, image: applyingImageIds },
    editing, startEditing, cancelEditing, setBoundary, addWord,
    mediaFor, player, toast,
    reportReasons, report,
  }
}

export type Review = ReturnType<typeof useReview>
