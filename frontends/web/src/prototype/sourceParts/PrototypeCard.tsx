// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { Badge, Button, Menu, StatusDot, Text, type MenuItem, type Tone } from '@/ui'
import type { CandidateSection } from '@/api/types'
import phrase from '@/ui/phrase.module.css'
import css from '@/screens/review/review.module.css'
import type { Card, CardStatus, Sentence } from './mockData'
import { phraseParts, snippet } from './model'

const DECISIONS: { status: Exclude<CardStatus, 'pending'>; label: string; kbd: string }[] = [
  { status: 'learn', label: 'Learn', kbd: '1' },
  { status: 'known', label: 'Know', kbd: '3' },
  { status: 'skip', label: 'Skip', kbd: '4' },
]
const SECTION_LABEL: Record<CandidateSection, string> = { ready: 'ready', extra: 'more new words', probably_known: 'probably known' }
const TONE: Record<CardStatus, Tone> = { pending: 'idle', learn: 'ok', known: 'off', skip: 'off' }

interface CardProps {
  card: Card
  sentence: Sentence
  /** Part label on the card: only in the whole-book view. */
  partLabel: string | null
  others: Sentence[]
  labelOfPart: (partId: string) => string
  onDecide: (status: CardStatus) => void
  onChoosePhrase: (sentenceId: string) => void
}

export function PrototypeCard({ card, sentence, partLabel, others, labelOfPart, onDecide, onChoosePhrase }: CardProps) {
  const [before, target, after] = phraseParts(sentence)
  const otherItems: MenuItem[] = others.map(s => ({
    label: snippet(s.text),
    hint: labelOfPart(s.partId),
    value: s.polished ? 'Polish' : undefined,
    onSelect: () => onChoosePhrase(s.id),
  }))
  const variant = (status: CardStatus) => (card.status === 'pending' ? status === 'learn' : card.status === status) ? 'fill' : 'soft'

  return (
    <article className={css.card} data-card-id={card.id}>
      <header className={css.cardHead}>
        <p className={css.phrase}>
          {before}<b className={`${phrase.target} ${phrase.targetCurrent}`}>{target}</b>{after}
        </p>
        <div className={css.meta}>
          <Text tone="soft">{card.lemma}</Text>
          {partLabel && <span>{partLabel}</span>}
        </div>
      </header>

      <div className={css.cardLeft}>
        <div className={css.decisions}>
          {DECISIONS.map(d => (
            <Button key={d.status} variant={variant(d.status)} kbd={d.kbd} onClick={() => onDecide(d.status)}>{d.label}</Button>
          ))}
        </div>
      </div>

      <div className={css.cardRight}>
        {sentence.polished
          ? <p className={css.definition}>{sentence.meaning}</p>
          : <div className={css.status}><Text tone="muted" size="s">Not generated yet</Text></div>}
        <div className={css.cardFoot}>
          <div className={css.facts}>
            <span>{SECTION_LABEL[card.section]}</span>
            {sentence.polished && <span>polished</span>}
          </div>
          {others.length > 0
            ? <Menu trigger={<Button variant="accent-link">Other phrases ({others.length})</Button>} items={otherItems} />
            : <Text tone="muted" size="s">No other phrases</Text>}
        </div>
      </div>
    </article>
  )
}

interface RowProps {
  card: Card
  sentence: Sentence
  partLabel: string | null
  onSelect: () => void
}

export function PrototypeRow({ card, sentence, partLabel, onSelect }: RowProps) {
  const rated = card.status !== 'pending'
  const [before, target, after] = phraseParts(sentence)
  return (
    <button type="button" className={rated ? `${css.queueItem} ${css.queueItemRated}` : css.queueItem} data-card-id={card.id} title={sentence.text} onClick={onSelect}>
      {rated && <StatusDot tone={TONE[card.status]} />}
      <span className={css.queueText}>{before}<span className={css.queueTarget}>{target}</span>{after}</span>
      {partLabel && <Badge>{partLabel}</Badge>}
    </button>
  )
}
