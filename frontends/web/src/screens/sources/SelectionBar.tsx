import { X } from 'lucide-react'
import { Button, IconButton } from '@/ui'
import css from './sources.module.css'

interface SelectionBarProps {
  count: number
  onMoveTo: () => void
  onProcess: () => void
  onDelete: () => void
  onClear: () => void
}

export function SelectionBar({ count, onMoveTo, onProcess, onDelete, onClear }: SelectionBarProps) {
  return (
    <div className={css.selectionBar} role="toolbar" aria-label="Selected sources">
      <span className={css.selectionCount} aria-live="polite">{count} selected</span>
      <div className={css.selectionActions}>
        <Button onClick={onMoveTo}>Move to…</Button>
        <Button onClick={onProcess}>Process</Button>
        <Button variant="danger-link" onClick={onDelete}>Delete</Button>
        <IconButton icon={X} label="Clear selection" onClick={onClear} />
      </div>
    </div>
  )
}
