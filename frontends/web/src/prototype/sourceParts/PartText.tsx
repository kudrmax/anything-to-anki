// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { useEffect, useRef } from 'react'
import css from '@/screens/review/review.module.css'
import local from './prototype.module.css'
import type { Card, Part } from './mockData'
import { phraseParts } from './model'

const SENTENCES_PER_PARAGRAPH = 5

interface PartTextProps {
  part: Part
  /** Label above the text: in the whole-book view the shown part changes with the card. */
  label: string | null
  cards: Card[]
  currentId: string | null
  onSelect: (cardId: string) => void
}

/** Text of one part with the card phrases marked, like SourceText. */
export function PartText({ part, label, cards, currentId, onSelect }: PartTextProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cardBySentence = new Map(cards.filter(c => c.partId === part.id).map(c => [c.sentenceId, c]))
  const paragraphs: (typeof part.sentences)[] = []
  part.sentences.forEach((s, i) => {
    if (i % SENTENCES_PER_PARAGRAPH === 0) paragraphs.push([])
    paragraphs[paragraphs.length - 1].push(s)
  })

  useEffect(() => {
    const container = containerRef.current
    const mark = container?.querySelector<HTMLElement>('[data-current="true"]')
    if (!container || !mark) return
    container.scrollTo({ top: mark.offsetTop - container.clientHeight / 2, behavior: 'smooth' })
  }, [currentId, part.id])

  return (
    <>
      {label && <div className={local.partLabel}>{label}</div>}
      <div ref={containerRef} className={css.source}>
        <div className={css.heading}>{part.title}</div>
        {paragraphs.map((sentences, p) => (
          <div key={p} className={css.block}>
            {sentences.map(s => {
              const card = cardBySentence.get(s.id)
              if (!card) return <span key={s.id}>{s.text} </span>
              const current = card.id === currentId
              const state = current ? css.markCurrent : card.status !== 'pending' ? css.markRated : css.markPending
              const [before, target, after] = phraseParts(s)
              return (
                <span key={s.id}>
                  <span className={current ? css.fragment : undefined}>
                    {before}
                    <mark className={`${css.mark} ${state}${current ? ` ${css.fragment}` : ''}`} data-current={current} onClick={() => onSelect(card.id)}>{target}</mark>
                    {after}
                  </span>{' '}
                </span>
              )
            })}
          </div>
        ))}
      </div>
    </>
  )
}
