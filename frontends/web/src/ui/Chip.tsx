import type { ButtonHTMLAttributes } from 'react'
import css from './Chip.module.css'

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  on?: boolean
  outlined?: boolean
  small?: boolean
}

export function Chip({ on = false, outlined = false, small = false, className, ...rest }: ChipProps) {
  const classes = [css.chip, on && css.on, outlined && !on && css.outlined, small && css.small, className].filter(Boolean).join(' ')
  return <button type="button" className={classes} aria-pressed={on} {...rest} />
}
