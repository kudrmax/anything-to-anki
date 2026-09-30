import css from './Segmented.module.css'

interface SegmentedProps<T extends string> {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

export function Segmented<T extends string>({ value, options, onChange }: SegmentedProps<T>) {
  return (
    <div className={css.segmented}>
      {options.map(option => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? `${css.item} ${css.on}` : css.item}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
