import type { ReactNode } from 'react'
import { Progress } from './Progress'
import css from './Stat.module.css'

interface StatProps {
  value: ReactNode
  label: string
  /** Доля 0..1 — шкала под подписью. */
  progress?: number
  hint?: ReactNode
  /** Текстовое значение вместо крупного числа. */
  small?: boolean
  /** Плитка на всю ширину сетки. */
  wide?: boolean
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <section className={css.grid}>{children}</section>
}

export function Stat({ value, label, progress, hint, small = false, wide = false }: StatProps) {
  return (
    <div className={wide ? `${css.stat} ${css.wide}` : css.stat}>
      <b className={small ? `${css.value} ${css.small}` : css.value}>{value}</b>
      <span className={css.label}>{label}</span>
      {progress !== undefined && <Progress value={progress} />}
      {hint && <span className={css.hint}>{hint}</span>}
    </div>
  )
}
