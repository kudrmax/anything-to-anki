import css from './Tabs.module.css'

interface TabsProps<T extends string> {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

export function Tabs<T extends string>({ value, options, onChange }: TabsProps<T>) {
  return (
    <div className={css.tabs} role="tablist">
      {options.map(option => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          className={option.value === value ? `${css.tab} ${css.on}` : css.tab}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
