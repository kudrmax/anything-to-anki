import { useEffect, useState } from 'react'
import type { StoredCandidate } from '@/api/types'
import { pickedIndices, toggled } from '@/lib/text/words'
import type { Review } from './useReview'

const sameWords = (a: readonly number[], b: readonly number[]): boolean =>
  a.length === b.length && a.every((word, i) => word === b[i])

/**
 * Выбор нового таргета карточки среди слов фразы, которую она показывает; начинается с нынешнего таргета.
 * Карточку с новым таргетом делает backend, она встаёт на место этой.
 */
export function useTargetEditor(candidate: StoredCandidate, review: Review) {
  const active = review.targetEditingId === candidate.phrase_id
  const target = candidate.phrase.target
  const [picked, setPicked] = useState<Set<number>>(() => new Set(target))
  const [saving, setSaving] = useState(false)

  // Открыли заново или сменилась фраза (polish, откат) — выбор снова с нынешнего таргета: старые номера слов ничего не значат.
  const phraseKey = `${candidate.phrase.text}\u0000${target.join(',')}`
  // eslint-disable-next-line react-hooks/exhaustive-deps -- target читается по phraseKey, массив меняется при каждом ответе
  useEffect(() => { setPicked(new Set(target)) }, [active, phraseKey])

  const words = pickedIndices(picked)
  const canSave = active && !saving && words.length > 0 && !sameWords(words, target)

  const save = async () => {
    if (!canSave) return
    setSaving(true)
    const changed = await review.changeTarget(candidate.phrase_id, words)
    setSaving(false)
    if (changed) review.cancelTarget()
  }

  return {
    active, picked, saving, canSave, save,
    toggleWord: (index: number) => setPicked(prev => toggled(prev, index)),
    start: () => review.startTarget(candidate.phrase_id),
    cancel: review.cancelTarget,
  }
}

export type TargetEditor = ReturnType<typeof useTargetEditor>
