import type { CSSProperties } from 'react'
import css from './Progress.module.css'

interface ProgressProps {
  /** Доля выполненного, 0..1. */
  value: number
  inline?: boolean
}

export function Progress({ value, inline = false }: ProgressProps) {
  const percent = `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
  return (
    <div className={inline ? `${css.progress} ${css.inline}` : css.progress} style={{ '--p': percent } as CSSProperties}>
      <i className={css.bar} />
    </div>
  )
}
