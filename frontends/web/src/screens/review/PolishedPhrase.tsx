import { WandSparkles } from 'lucide-react'
import type { StoredCandidate } from '@/api/types'
import { computeDiff } from '@/lib/text/diff'
import { highlightParts } from '@/lib/text/meaning'
import { Button, IconButton, Menu } from '@/ui'
import type { Review } from './useReview'
import css from './review.module.css'

interface PolishedPhraseProps {
  candidate: StoredCandidate
  review: Review
}

/** Иконка у фразы, которую упростил AI: под ней оригинал из книги, правки и откат. */
export function PolishedPhrase({ candidate, review }: PolishedPhraseProps) {
  const polishing = candidate.polish_status === 'queued' || candidate.polish_status === 'running'
  const polished = candidate.polished_fragment
  if (polishing) return <IconButton icon={WandSparkles} label="Polishing the phrase…" busy />
  if (!polished) return null

  const id = candidate.id
  const reverted = candidate.polish_reverted
  return (
    <Menu
      trigger={<IconButton icon={WandSparkles} label="Phrase polished — see original" />}
      items={[]}
      footer={close => (
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
            <Button onClick={() => { void review.setPolishReverted(id, !reverted); close() }}>
              {reverted ? 'Use polished phrase' : 'Revert to original'}
            </Button>
            <Button variant="link" onClick={() => { void review.polishAgain(id); close() }}>Polish again</Button>
          </div>
        </div>
      )}
    />
  )
}
