import type { CandidateStatus, StoredCandidate } from '@/api/types'
import { highlightParts } from '@/lib/text/meaning'
import { StatusDot, type Tone } from '@/ui'
import phrase from '@/ui/phrase.module.css'
import css from './review.module.css'

const TONE: Record<CandidateStatus, Tone> = { pending: 'idle', learn: 'ok', known: 'off', skip: 'off' }

interface PhraseRowProps {
  candidate: StoredCandidate
  onSelect: (id: number) => void
}

/** Фраза в очереди: одна строка, полный текст — в подсказке. */
export function PhraseRow({ candidate, onSelect }: PhraseRowProps) {
  const rated = candidate.status !== 'pending'
  const classes = [css.queueItem, rated && css.queueItemRated].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} data-candidate-id={candidate.id} title={candidate.context_fragment} onClick={() => onSelect(candidate.id)}>
      {rated && <StatusDot tone={TONE[candidate.status]} />}
      <span className={css.queueText}>
        {highlightParts(candidate.context_fragment, candidate.lemma, candidate.surface_form).map((part, i) =>
          part.target ? <b key={i} className={rated ? `${phrase.target} ${phrase.targetRated}` : phrase.target}>{part.text}</b> : part.text,
        )}
      </span>
    </button>
  )
}
