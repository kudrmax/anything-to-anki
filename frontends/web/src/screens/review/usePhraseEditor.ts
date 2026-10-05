import { useState } from 'react'
import type { StoredCandidate } from '@/api/types'
import type { Review } from './useReview'

/** Ручная правка фразы карточки: открывается двойным кликом или из меню карандаша. */
export function usePhraseEditor(candidate: StoredCandidate, review: Review) {
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const start = () => {
    window.getSelection()?.removeAllRanges()
    setDraft(candidate.phrase)
  }

  const save = async () => {
    if (draft === null || saving) return
    if (draft.trim() === candidate.phrase.trim()) {
      setDraft(null)
      return
    }
    setSaving(true)
    const saved = await review.editPhrase(candidate.id, draft)
    setSaving(false)
    if (saved) setDraft(null)
  }

  return { draft, setDraft, saving, start, save, cancel: () => setDraft(null) }
}

export type PhraseEditor = ReturnType<typeof usePhraseEditor>
