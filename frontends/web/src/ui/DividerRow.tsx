import type { HTMLAttributes, ReactNode } from 'react'
import css from './DividerRow.module.css'

interface DividerRowProps extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  label: ReactNode
  hint?: ReactNode
  /** Элемент перед подписью, например ручка перетаскивания. */
  lead?: ReactNode
  compact?: boolean
  last?: boolean
  state?: 'dragging' | 'target'
  children?: ReactNode
}

export function DividerRow({ label, hint, lead, compact = false, last = false, state, children, ...rest }: DividerRowProps) {
  const classes = [css.row, compact && css.compact, last && css.last, state && css[state]].filter(Boolean).join(' ')
  return (
    <div className={classes} {...rest}>
      {lead}
      <div className={css.text}>
        <div>{label}</div>
        {hint && <div className={css.hint}>{hint}</div>}
      </div>
      {children}
    </div>
  )
}

export function GroupLabel({ children, flush = false }: { children: ReactNode; flush?: boolean }) {
  return <div className={flush ? `${css.group} ${css.flush}` : css.group}>{children}</div>
}
