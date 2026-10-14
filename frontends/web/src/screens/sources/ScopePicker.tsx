import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { Button, Icon, Modal } from '@/ui'
import css from './sources.module.css'

interface ScopePickerProps {
  title: string
  open: boolean
  onOpen: () => void
  onClose: () => void
  /** Статистика и дерево. */
  children: ReactNode
}

/** Телефон: левая колонка складывается в кнопку над списком и открывается листом снизу. */
export function ScopePicker({ title, open, onOpen, onClose, children }: ScopePickerProps) {
  return (
    <>
      <button type="button" className={`${css.scopePicker} ${css.phoneOnly}`} aria-haspopup="dialog" aria-expanded={open} onClick={onOpen}>
        <span>{title}</span>
        <Icon as={ChevronDown} size="s" />
      </button>
      {open && (
        <Modal sheet title="Collections" onClose={onClose} footer={<Button variant="link" onClick={onClose}>Close</Button>}>
          <div className={css.pickerBody}>{children}</div>
        </Modal>
      )}
    </>
  )
}
