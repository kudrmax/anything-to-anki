import type { CardPhrase } from '@/api/types'
import { keepFocusOnMouseDown } from '@/lib/mouseFocus'
import { phraseParts } from '@/lib/text/phraseParts'
import css from './review.module.css'

interface ClozePhraseProps {
  phrase: CardPhrase
  hidden: number[]
  onToggle: (index: number) => void
}

/** Фраза в режиме разметки cloze: каждое слово — кнопка, скрытые слова в пунктирной рамке. */
export function ClozePhrase({ phrase, hidden, onToggle }: ClozePhraseProps) {
  return (
    <p className={`${css.phrase} ${css.clozeEdit}`}>
      {phraseParts(phrase, new Set(hidden)).map((part, i) => {
        const word = part.word
        if (word === null) return part.text
        const classes = [
          css.clozeWord,
          part.target && css.clozeWordTarget,
          part.hidden && css.clozeGap,
          part.hidden && !part.target && css.clozeWordExtra,
        ].filter(Boolean).join(' ')
        return (
          <button key={i} type="button" className={classes} aria-pressed={part.hidden} onMouseDown={keepFocusOnMouseDown} onClick={() => onToggle(word)}>
            {part.text}
          </button>
        )
      })}
    </p>
  )
}
