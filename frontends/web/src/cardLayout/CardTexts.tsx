import { useState } from 'react'
import type { EnrichmentStatus, StoredCandidate } from '@/api/types'
import { meaningParts } from '@/lib/text/meaning'
import { targetText } from '@/lib/text/phraseParts'
import { Spinner, Text } from '@/ui'
import type { CardBlockContext } from './CardBlockContext'
import css from './cardLayout.module.css'

/** Текст значения: **жирные** участки и вхождения изучаемого слова. */
export function RichText({ text, candidate }: { text: string; candidate: StoredCandidate }) {
  return (
    <>
      {meaningParts(text, candidate.lemma, targetText(candidate.phrase)).map((part, i) =>
        part.target ? <b key={i} className={css.richTarget}>{part.text}</b> : part.bold ? <b key={i}>{part.text}</b> : part.text,
      )}
    </>
  )
}

export function StatusText({ status, labels, error }: { status: EnrichmentStatus | undefined; labels: Partial<Record<EnrichmentStatus, string>>; error?: string | null }) {
  if (!status || !labels[status]) return null
  return (
    <span className={css.status} title={error ?? undefined}>
      {status === 'running' && <Spinner />}
      <Text tone={status === 'failed' ? 'err' : 'muted'} size="s">{labels[status]}</Text>
    </span>
  )
}

/** Примеры: при наведении (на телефоне — по тапу) пример можно поставить вместо фразы. */
export function Examples({ lines, ctx }: { lines: string[]; ctx: CardBlockContext }) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <ul className={css.examples}>
      {lines.map((line, i) => (
        <li key={i} className={open === i ? `${css.example} ${css.exampleOpen}` : css.example} onClick={() => setOpen(i)}>
          <span><RichText text={line} candidate={ctx.candidate} /></span>
          <button type="button" className={css.useExample} onClick={() => ctx.useExample(line.trim())}>
            Use as phrase
          </button>
        </li>
      ))}
    </ul>
  )
}
