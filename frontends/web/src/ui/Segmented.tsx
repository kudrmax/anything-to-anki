import type { MouseEvent } from 'react'
import css from './Segmented.module.css'

interface SegmentedOption<T extends string> {
  value: T
  label: string
  disabled?: boolean
}

interface SegmentedProps<T extends string> {
  value: T
  options: SegmentedOption<T>[]
  onChange: (value: T) => void
  className?: string
  onOptionMouseDown?: (e: MouseEvent<HTMLButtonElement>) => void
}

export function Segmented<T extends string>({ value, options, onChange, className, onOptionMouseDown }: SegmentedProps<T>) {
  return (
    <div className={[css.segmented, className].filter(Boolean).join(' ')}>
      {options.map(option => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? `${css.item} ${css.on}` : css.item}
          aria-pressed={option.value === value}
          disabled={option.disabled}
          onMouseDown={onOptionMouseDown}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
