import type { StoredCandidate } from '@/api/types'
import { computeDiff } from '@/lib/text/diff'
import { highlightParts } from '@/lib/text/meaning'
import { Button } from '@/ui'
import type { Review } from './useReview'
import css from './review.module.css'

interface PolishComparisonProps {
  candidate: StoredCandidate
  polished: string
  review: Review
  onDone: () => void
}

/** Фраза, которую упростил AI или поправил пользователь: оригинал из книги, правки и откат. */
export function PolishComparison({ candidate, polished, review, onDone }: PolishComparisonProps) {
  const id = candidate.id
  const reverted = candidate.polish_reverted
  return (
    <div className={css.polish}>
      <p className={css.polishLabel}>Original from the book</p>
      <p className={css.polishText}>
        {highlightParts(candidate.context_fragment, candidate.lemma, candidate.surface_form).map((part, i) =>
          part.target ? <b key={i}>{part.text}</b> : part.text,
        )}
      </p>
      <p className={css.polishLabel}>Changes</p>
      <p className={css.polishText}>
        {computeDiff(candidate.context_fragment, polished).map((segment, i) =>
          segment.type === 'same' ? segment.text
            : <span key={i} className={segment.type === 'added' ? css.added : css.removed}>{segment.text}</span>,
        )}
      </p>
      <div className={css.polishActions}>
        <Button onClick={() => { void review.setPolishReverted(id, !reverted); onDone() }}>
          {reverted ? 'Use polished phrase' : 'Revert to original'}
        </Button>
        <Button variant="link" onClick={() => { void review.polishAgain(id); onDone() }}>Polish again</Button>
      </div>
    </div>
  )
}
