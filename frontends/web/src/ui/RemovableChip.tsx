import { X } from 'lucide-react'
import { Icon } from './Icon'
import css from './RemovableChip.module.css'

interface RemovableChipProps {
  label: string
  onRemove: () => void
  disabled?: boolean
}

/** Значение в списке, которое удаляется только крестиком. */
export function RemovableChip({ label, onRemove, disabled = false }: RemovableChipProps) {
  return (
    <span className={css.chip}>
      {label}
      <button type="button" className={css.remove} aria-label={`Remove ${label}`} title="Remove" disabled={disabled} onClick={onRemove}>
        <Icon as={X} size="s" />
      </button>
    </span>
  )
}
