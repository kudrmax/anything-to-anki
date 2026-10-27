import type { CardPhrase } from '@/api/types'
import { phraseParts } from '@/lib/text/phraseParts'
import { Button } from '@/ui'
import css from './review.module.css'

interface UnknownWordsPickerProps {
  phrase: CardPhrase
  selected: ReadonlySet<number>
  onToggle: (word: number) => void
  onSend: () => void
}

/** Фраза карточки, где каждое слово — кнопка: незнакомые слова отмечаются прямо в тексте. */
export function UnknownWordsPicker({ phrase, selected, onToggle, onSend }: UnknownWordsPickerProps) {
  const count = selected.size
  return (
    <div className={css.unknown}>
      <p className={css.unknownHint}>Pick the words you don't know</p>
      <p className={css.unknownPhrase}>
        {phraseParts(phrase).map((part, i) => {
          const word = part.word
          if (word === null) return part.text
          const classes = [css.unknownWord, part.target && css.unknownTarget, selected.has(word) && css.unknownPicked]
            .filter(Boolean).join(' ')
          return (
            <button key={i} type="button" className={classes} aria-pressed={selected.has(word)} onClick={() => onToggle(word)}>
              {part.text}
            </button>
          )
        })}
      </p>
      <Button variant="fill" wide disabled={count === 0} onClick={onSend}>
        {count > 1 ? `Mark ${count} words as unknown` : 'Mark as unknown'}
      </Button>
    </div>
  )
}
