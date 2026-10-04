import { phraseWords } from '@/lib/text/words'
import { Chip } from './Chip'
import css from './WordPicker.module.css'

interface WordPickerProps {
  phrase: string
  selected: ReadonlySet<number>
  onToggle: (index: number) => void
}

export function WordPicker({ phrase, selected, onToggle }: WordPickerProps) {
  return (
    <div className={css.words}>
      {phraseWords(phrase).map((word, i) => (
        <Chip key={i} small on={selected.has(i)} onClick={() => onToggle(i)}>{word}</Chip>
      ))}
    </div>
  )
}
