import { useState, type KeyboardEvent, type MouseEvent, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { Button, Icon, Modal } from '@/ui'
import css from './sources.module.css'

interface ScopePickerProps {
  title: string
  /** Статистика и дерево: выбор узла в дереве закрывает лист. */
  children: ReactNode
}

const choseNode = (target: EventTarget) => target instanceof Element && target.closest('[role="treeitem"]') !== null

/** Телефон: левая колонка складывается в кнопку над списком и открывается листом снизу. */
export function ScopePicker({ title, children }: ScopePickerProps) {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  const onClick = (e: MouseEvent) => { if (choseNode(e.target)) close() }
  const onKeyDown = (e: KeyboardEvent) => { if (e.key === 'Enter' && choseNode(e.target)) close() }

  return (
    <>
      <button type="button" className={`${css.scopePicker} ${css.phoneOnly}`} aria-haspopup="dialog" onClick={() => setOpen(true)}>
        <span>{title}</span>
        <Icon as={ChevronDown} size="s" />
      </button>
      {open && (
        <Modal sheet title="Collections" onClose={close} footer={<Button variant="link" onClick={close}>Close</Button>}>
          <div className={css.pickerBody} onClick={onClick} onKeyDown={onKeyDown}>{children}</div>
        </Modal>
      )}
    </>
  )
}
