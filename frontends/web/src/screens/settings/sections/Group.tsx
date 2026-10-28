import type { ReactNode } from 'react'
import css from '../settings.module.css'

interface GroupProps {
  title?: string
  hint?: ReactNode
  children: ReactNode
}

/** Подгруппа настроек внутри раздела; без заголовка — вводная часть раздела. */
export function Group({ title, hint, children }: GroupProps) {
  return (
    <section className={css.group}>
      {title && <h3 className={css.groupTitle}>{title}</h3>}
      {hint && <p className={css.groupHint}>{hint}</p>}
      {children}
    </section>
  )
}
