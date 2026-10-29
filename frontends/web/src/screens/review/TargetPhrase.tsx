import type { CardPhrase } from '@/api/types'
import { keepFocusOnMouseDown } from '@/lib/mouseFocus'
import { phraseParts, touchesMarks, wordGroups } from '@/lib/text/phraseParts'
import css from './review.module.css'

interface TargetPhraseProps {
  phrase: CardPhrase
  picked: ReadonlySet<number>
  onToggle: (index: number) => void
}

/** Фраза в режиме выбора таргета: каждое слово — кнопка, выбранные выглядят как таргет карточки. */
export function TargetPhrase({ phrase, picked, onToggle }: TargetPhraseProps) {
  return (
    <p className={`${css.phrase} ${css.clozeEdit}`}>
      {wordGroups(phraseParts(phrase)).map((group, g) => (
        <span key={g} className={css.wordGroup}>
          {group.map((part, i) => {
            const word = part.word
            if (word === null) return part.text
            const on = picked.has(word)
            const marks = touchesMarks(group, i)
            const classes = [
              css.clozeWord,
              on && css.clozeWordPicked,
              marks.before && css.markBefore,
              marks.after && css.markAfter,
            ].filter(Boolean).join(' ')
            return (
              <button
                key={i}
                type="button"
                className={classes}
                aria-pressed={on}
                onMouseDown={keepFocusOnMouseDown}
                onClick={() => onToggle(word)}
              >
                {part.text}
              </button>
            )
          })}
        </span>
      ))}
    </p>
  )
}
