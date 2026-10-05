import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { ClozeDraft, ClozeHintKind, ClozePreview, StoredCandidate } from '@/api/types'
import { clozeSaveRequest } from './clozeDraft'
import type { Review } from './useReview'

const FAILED_PREVIEW = 'Failed to preview the cloze'

const isAbort = (e: unknown): boolean => e instanceof DOMException && e.name === 'AbortError'

/**
 * Разметка cloze текущей карточки: какие слова скрыть и какая подсказка.
 * Слова, умолчания, доступные подсказки и лицевую сторону считает backend — здесь только черновик.
 * Каждое изменение черновика перезапрашивает превью; новый запрос отменяет тот, что ещё в пути.
 * Сменилась фраза карточки (polish, откат, фоновая генерация) — черновик сбрасывается к умолчаниям новой фразы.
 */
export function useClozeEditor(candidate: StoredCandidate, review: Review) {
  const active = review.clozeEditingId === candidate.id
  const [draft, setDraft] = useState<ClozeDraft | null>(null)
  const [preview, setPreview] = useState<ClozePreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  const requestPreview = useCallback(async (request: Partial<ClozeDraft>) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    try {
      const next = await api.previewCloze(candidate.id, request, controller.signal)
      if (inFlight.current !== controller) return
      setPreview(next)
      setDraft({ hidden_word_indices: next.hidden_word_indices, hint_kind: next.hint_kind, custom_hint: next.custom_hint })
      setError(null)
    } catch (e) {
      if (isAbort(e) || inFlight.current !== controller) return
      setError(e instanceof Error ? e.message : FAILED_PREVIEW)
    } finally {
      if (inFlight.current === controller) inFlight.current = null
    }
  }, [candidate.id])

  const phrase = candidate.phrase
  useEffect(() => {
    if (!active) return
    void requestPreview({})
    return () => {
      inFlight.current?.abort()
      inFlight.current = null
      setDraft(null)
      setPreview(null)
      setError(null)
    }
    // phrase: новая фраза — новые слова и индексы, старый черновик к ней не относится.
  }, [active, phrase, requestPreview])

  const change = (patch: Partial<ClozeDraft>) => {
    if (!draft) return
    const next = { ...draft, ...patch }
    setDraft(next)
    void requestPreview(next)
  }

  const toggleWord = (index: number) => {
    if (!draft) return
    const hidden = draft.hidden_word_indices
    change({
      hidden_word_indices: hidden.includes(index) ? hidden.filter(i => i !== index) : [...hidden, index].sort((a, b) => a - b),
    })
  }

  const setHintKind = (kind: ClozeHintKind) => change({ hint_kind: kind })
  const setCustomHint = (text: string) => change({ custom_hint: text })

  const canSave = draft !== null && preview !== null && !saving && preview.can_save

  const save = async () => {
    if (!draft || !preview || !canSave) return
    setSaving(true)
    try {
      await review.saveCloze(candidate.id, clozeSaveRequest(draft, preview))
    } finally {
      setSaving(false)
    }
  }

  return {
    active, draft, preview, error, saving, canSave,
    toggleWord, setHintKind, setCustomHint, save,
    start: () => review.startCloze(candidate.id),
    cancel: review.cancelCloze,
  }
}

export type ClozeEditor = ReturnType<typeof useClozeEditor>
