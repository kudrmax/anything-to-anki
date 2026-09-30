import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import { Check } from 'lucide-react'
import { Icon } from './Icon'
import css from './Menu.module.css'

export interface MenuItem {
  label: string
  onSelect: () => void
  danger?: boolean
  selected?: boolean
  disabled?: boolean
}

interface MenuProps {
  trigger: ReactNode
  items: MenuItem[]
  /** Нижняя часть меню, например поле ввода. Получает функцию закрытия. */
  footer?: (close: () => void) => ReactNode
  emptyText?: string
  align?: 'start' | 'end'
  openOn?: 'click' | 'contextmenu'
}

export function Menu({ trigger, items, footer, emptyText, align = 'end', openOn = 'click' }: MenuProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const close = () => setOpen(false)
  const triggerProps = openOn === 'click'
    ? { onClick: (e: MouseEvent) => { e.stopPropagation(); setOpen(o => !o) } }
    : { onContextMenu: (e: MouseEvent) => { e.preventDefault(); setOpen(true) } }

  return (
    <span className={css.root} ref={rootRef}>
      <span className={css.trigger} {...triggerProps}>{trigger}</span>
      {open && (
        <div className={`${css.menu} ${css[align]}`} role="menu" onClick={e => e.stopPropagation()}>
          {items.length === 0 && emptyText && <div className={css.empty}>{emptyText}</div>}
          {items.map((item, index) => (
            <button
              key={index}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              className={item.danger ? `${css.item} ${css.danger}` : css.item}
              onClick={() => { close(); item.onSelect() }}
            >
              <span className={css.label}>{item.label}</span>
              {item.selected && <Icon as={Check} size="s" />}
            </button>
          ))}
          {footer && <div className={css.footer}>{footer(close)}</div>}
        </div>
      )}
    </span>
  )
}
