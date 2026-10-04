import { useState, type KeyboardEvent } from 'react'
import type { StoredCandidate } from '@/api/types'
import { highlightParts } from '@/lib/text/meaning'
import type { Review } from './useReview'
import phrase from '@/ui/phrase.module.css'
import css from './review.module.css'

interface CardPhraseProps {
  candidate: StoredCandidate
  review: Review
}

/** Фраза карточки: двойной клик открывает ручную правку, Enter сохраняет, Esc отменяет. */
export function CardPhrase({ candidate, review }: CardPhraseProps) {
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const editable = Boolean(review.source?.can_polish_phrases)

  const startEditing = () => {
    if (!editable) return
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

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void save()
    } else if (e.key === 'Escape') {
      e.stopPropagation()
      setDraft(null)
    }
  }

  if (draft !== null) {
    return (
      // Невидимая копия текста в той же ячейке грида растит поле по содержимому.
      <div className={`${css.phrase} ${css.phraseEdit}`} data-value={draft}>
        <textarea
          value={draft}
          autoFocus
          rows={1}
          readOnly={saving}
          aria-label="Edit phrase"
          onFocus={e => e.target.setSelectionRange(e.target.value.length, e.target.value.length)}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => void save()}
        />
      </div>
    )
  }

  return (
    <p className={css.phrase} title={editable ? 'Double-click to edit' : undefined} onDoubleClick={startEditing}>
      {highlightParts(candidate.phrase, candidate.lemma, candidate.surface_form).map((part, i) =>
        part.target ? <b key={i} className={`${phrase.target} ${phrase.targetCurrent}`}>{part.text}</b> : part.text,
      )}
    </p>
  )
}
