import type { ButtonHTMLAttributes } from 'react'
import { Kbd } from './Kbd'
import { Spinner } from './Spinner'
import css from './Button.module.css'

type Variant = 'soft' | 'fill' | 'link' | 'accent-link' | 'danger-link'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  busy?: boolean
  kbd?: string
  wide?: boolean
  /** Сколько штук затронет нажатие: счётчик в кнопке, а не текст в подписи. */
  count?: number
}

export function Button({ variant = 'soft', busy = false, kbd, wide = false, count, disabled, children, className, ...rest }: ButtonProps) {
  const classes = [css.button, css[variant], wide && css.wide, className].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} disabled={disabled || busy} {...rest}>
      {busy && <Spinner />}
      {children}
      {count !== undefined && <span className={css.count}>{count}</span>}
      {kbd && <Kbd>{kbd}</Kbd>}
    </button>
  )
}
