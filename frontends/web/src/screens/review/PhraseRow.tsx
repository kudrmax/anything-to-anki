import type { CandidateStatus, StoredCandidate } from '@/api/types'
import { FREQ_BAND_LABEL, highlightParts } from '@/lib/text/meaning'
import { Row, type Tone } from '@/ui'
import { PhraseDetails } from './PhraseDetails'
import type { Review } from './useReview'
import phrase from '@/ui/phrase.module.css'

const TONE: Record<CandidateStatus, Tone> = { pending: 'idle', learn: 'ok', known: 'off', skip: 'off' }

interface PhraseRowProps {
  candidate: StoredCandidate
  current: boolean
  review: Review
}

export function PhraseRow({ candidate, current, review }: PhraseRowProps) {
  const dimmed = !current && (candidate.status === 'known' || candidate.status === 'skip')
  const targetClass = [phrase.target, current && phrase.targetCurrent, dimmed && phrase.targetRated].filter(Boolean).join(' ')
  const kind = candidate.is_phrasal_verb ? 'phrasal' : candidate.cefr_level
  const frequency = candidate.frequency_band ? FREQ_BAND_LABEL[candidate.frequency_band]?.toLowerCase() : null

  return (
    <Row
      tone={TONE[candidate.status]}
      dim={dimmed}
      current={current}
      dataId={candidate.id}
      onClick={() => review.setCurrentId(candidate.id)}
      title={highlightParts(candidate.context_fragment, candidate.lemma, candidate.surface_form).map((part, i) =>
        part.target ? <b key={i} className={targetClass}>{part.text}</b> : part.text,
      )}
      trailing={!current && [kind, frequency].filter(Boolean).join(' · ')}
    >
      {current && <PhraseDetails candidate={candidate} review={review} />}
    </Row>
  )
}
