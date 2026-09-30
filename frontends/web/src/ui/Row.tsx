import type { MouseEvent, ReactNode } from 'react'
import { StatusDot, type Tone } from './StatusDot'
import css from './Row.module.css'

interface RowProps {
  tone?: Tone
  title: ReactNode
  meta?: ReactNode
  /** Продолжение подписи, видимое только при наведении на строку. */
  hoverMeta?: ReactNode
  trailing?: ReactNode
  /** Видны только при наведении на строку. */
  actions?: ReactNode
  /** Раскрытая строка: поверхность с рамкой и крупный заголовок. */
  current?: boolean
  dim?: boolean
  onClick?: () => void
  onMouseEnter?: () => void
  onMouseLeave?: () => void
  /** Раскрытое содержимое под заголовком. */
  children?: ReactNode
  dataId?: number
}

const stop = (e: MouseEvent) => e.stopPropagation()

export function Row({ tone, title, meta, hoverMeta, trailing, actions, current = false, dim = false, onClick, onMouseEnter, onMouseLeave, children, dataId }: RowProps) {
  const classes = [css.row, current && css.current, dim && css.dim, onClick && !current && css.clickable].filter(Boolean).join(' ')
  return (
    <div className={classes} data-candidate-id={dataId} onClick={onClick} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
      {tone && <span className={css.dot}><StatusDot tone={tone} /></span>}
      <div className={css.body}>
        <div className={css.title}>{title}</div>
        {(meta || hoverMeta) && (
          <div className={css.meta}>
            {meta}
            {hoverMeta && <span className={css.hoverOnly} onClick={stop}>{hoverMeta}</span>}
          </div>
        )}
        {children}
      </div>
      {actions && <div className={css.actions} onClick={stop}>{actions}</div>}
      {trailing && <div className={css.trailing} onClick={stop}>{trailing}</div>}
    </div>
  )
}
