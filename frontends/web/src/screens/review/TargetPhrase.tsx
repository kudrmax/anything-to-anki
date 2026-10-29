import type { CardPhrase } from '@/api/types'
import { keepFocusOnMouseDown } from '@/lib/mouseFocus'
import { phraseParts } from '@/lib/text/phraseParts'
import phrase from '@/ui/phrase.module.css'
import css from './review.module.css'

interface TargetPhraseProps {
  phrase: CardPhrase
  picked: ReadonlySet<number>
  onToggle: (index: number) => void
}

/** Фраза в режиме выбора таргета: каждое слово — кнопка, выбранные выглядят как таргет карточки. */
export function TargetPhrase({ phrase: shown, picked, onToggle }: TargetPhraseProps) {
  return (
    <p className={`${css.phrase} ${css.clozeEdit}`}>
      {phraseParts(shown).map((part, i) => {
        const word = part.word
        if (word === null) return part.text
        const on = picked.has(word)
        return (
          <button
            key={i}
            type="button"
            className={on ? `${css.clozeWord} ${phrase.target} ${phrase.targetCurrent}` : css.clozeWord}
            aria-pressed={on}
            onMouseDown={keepFocusOnMouseDown}
            onClick={() => onToggle(word)}
          >
            {part.text}
          </button>
        )
      })}
    </p>
  )
}
