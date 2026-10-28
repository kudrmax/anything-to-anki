import { X } from 'lucide-react'
import { Icon } from './Icon'
import css from './RemovableChip.module.css'

interface RemovableChipProps {
  label: string
  /** Второстепенные факты о значении, например часть речи: каждый своим тихим элементом. */
  details?: string[]
  onRemove: () => void
  disabled?: boolean
}

/** Значение в списке, которое удаляется только крестиком. */
export function RemovableChip({ label, details = [], onRemove, disabled = false }: RemovableChipProps) {
  return (
    <span className={css.chip}>
      {label}
      {details.map(detail => <span key={detail} className={css.detail}>{detail}</span>)}
      <button type="button" className={css.remove} aria-label={['Remove', label, ...details].join(' ')} title="Remove" disabled={disabled} onClick={onRemove}>
        <Icon as={X} size="s" />
      </button>
    </span>
  )
}
