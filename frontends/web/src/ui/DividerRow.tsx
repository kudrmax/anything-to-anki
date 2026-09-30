import type { ReactNode } from 'react'
import css from './DividerRow.module.css'

interface DividerRowProps {
  label: ReactNode
  hint?: ReactNode
  compact?: boolean
  last?: boolean
  children?: ReactNode
}

export function DividerRow({ label, hint, compact = false, last = false, children }: DividerRowProps) {
  const classes = [css.row, compact && css.compact, last && css.last].filter(Boolean).join(' ')
  return (
    <div className={classes}>
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
