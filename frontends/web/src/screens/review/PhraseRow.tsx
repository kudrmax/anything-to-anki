import type { CandidateStatus, StoredCandidate } from '@/api/types'
import { highlightParts } from '@/lib/text/meaning'
import { StatusDot, type Tone } from '@/ui'
import css from './review.module.css'

const TONE: Record<CandidateStatus, Tone> = { pending: 'idle', learn: 'ok', known: 'off', skip: 'off' }

interface PhraseRowProps {
  candidate: StoredCandidate
  /** Место фразы в списке, начиная с 1. */
  position: number
  onSelect: (id: number) => void
}

/** Свёрнутая фраза в очереди. */
export function PhraseRow({ candidate, position, onSelect }: PhraseRowProps) {
  const rated = candidate.status !== 'pending'
  const classes = [css.queueItem, rated && css.queueItemRated].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} data-candidate-id={candidate.id} title={candidate.context_fragment} onClick={() => onSelect(candidate.id)}>
      <span className={css.queueMark}>{rated ? <StatusDot tone={TONE[candidate.status]} /> : position}</span>
      <span className={css.queueText}>
        {highlightParts(candidate.context_fragment, candidate.lemma, candidate.surface_form).map((part, i) =>
          part.target ? <b key={i} className={css.queueTarget}>{part.text}</b> : part.text,
        )}
      </span>
    </button>
  )
}
