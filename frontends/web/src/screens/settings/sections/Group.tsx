import { useState, type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Icon } from '@/ui'
import css from '../settings.module.css'

interface GroupProps {
  title?: string
  hint?: ReactNode
  /** Редкая настройка: свёрнута, пока её не откроют. */
  collapsible?: boolean
  children: ReactNode
}

/** Подгруппа настроек внутри раздела; без заголовка — вводная часть раздела. */
export function Group({ title, hint, collapsible = false, children }: GroupProps) {
  const [open, setOpen] = useState(!collapsible)
  return (
    <section className={css.group}>
      {title && collapsible && (
        <button type="button" className={css.groupToggle} aria-expanded={open} onClick={() => setOpen(!open)}>
          <Icon as={ChevronRight} size="s" />
          <h3 className={css.groupTitle}>{title}</h3>
        </button>
      )}
      {title && !collapsible && <h3 className={css.groupTitle}>{title}</h3>}
      {hint && <p className={css.groupHint}>{hint}</p>}
      {open && children}
    </section>
  )
}
