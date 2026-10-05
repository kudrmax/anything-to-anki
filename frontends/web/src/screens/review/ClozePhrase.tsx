import type { ClozePreview } from '@/api/types'
import { keepFocusOnMouseDown } from '@/lib/mouseFocus'
import css from './review.module.css'

interface ClozePhraseProps {
  preview: ClozePreview
  hidden: number[]
  onToggle: (index: number) => void
}

/** Фраза в режиме разметки cloze: каждое слово — кнопка, скрытые слова в пунктирной рамке. */
export function ClozePhrase({ preview, hidden, onToggle }: ClozePhraseProps) {
  return (
    <p className={`${css.phrase} ${css.clozeEdit}`}>
      {preview.words.map(word => {
        const isHidden = hidden.includes(word.index)
        const classes = [
          css.clozeWord,
          word.is_target && css.clozeWordTarget,
          isHidden && css.clozeGap,
          isHidden && !word.is_target && css.clozeWordExtra,
        ].filter(Boolean).join(' ')
        return (
          <button key={word.index} type="button" className={classes} aria-pressed={isHidden} onMouseDown={keepFocusOnMouseDown} onClick={() => onToggle(word.index)}>
            {word.text}
          </button>
        )
      })}
    </p>
  )
}
