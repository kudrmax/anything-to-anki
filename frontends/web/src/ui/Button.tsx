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
}

export function Button({ variant = 'soft', busy = false, kbd, wide = false, disabled, children, className, ...rest }: ButtonProps) {
  const classes = [css.button, css[variant], wide && css.wide, className].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} disabled={disabled || busy} {...rest}>
      {busy && <Spinner />}
      {children}
      {kbd && <Kbd>{kbd}</Kbd>}
    </button>
  )
}
