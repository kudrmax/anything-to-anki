import type { Shown, StoredCandidate } from '@/api/types'
import { phraseParts } from '@/lib/text/phraseParts'
import { Badge, StatusDot, type Tone } from '@/ui'
import css from './review.module.css'

// Точка — только у разобранной карточки; разобранная со статусом new — пропущенная фраза.
const TONE: Record<Shown['status'], Tone> = { new: 'off', learn: 'ok', learning: 'ok', known: 'off' }

interface PhraseRowProps {
  candidate: StoredCandidate
  onSelect: (id: number) => void
  current?: boolean
}

/** Свёрнутая фраза в очереди: одна строка, полный текст — в подсказке. */
export function PhraseRow({ candidate, onSelect, current = false }: PhraseRowProps) {
  const rated = candidate.is_done
  const classes = [css.queueItem, rated && css.queueItemRated, current && css.queueItemCurrent].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} data-candidate-id={candidate.phrase_id} title={candidate.phrase.text} onClick={() => onSelect(candidate.phrase_id)}>
      {rated && <StatusDot tone={TONE[candidate.shown.status]} />}
      <span className={css.queueText}>
        {phraseParts(candidate.phrase).map((part, i) =>
          part.target ? <span key={i} className={css.queueTarget}>{part.text}</span> : part.text,
        )}
      </span>
      {candidate.cloze && <Badge>cloze</Badge>}
    </button>
  )
}
