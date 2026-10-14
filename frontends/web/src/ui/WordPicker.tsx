import { Chip } from './Chip'
import css from './WordPicker.module.css'

interface WordPickerProps {
  words: string[]
  selected: ReadonlySet<number>
  onToggle: (index: number) => void
}

export function WordPicker({ words, selected, onToggle }: WordPickerProps) {
  return (
    <div className={css.words}>
      {words.map((word, i) => (
        <Chip key={i} small on={selected.has(i)} onClick={() => onToggle(i)}>{word}</Chip>
      ))}
    </div>
  )
}
