import type { ButtonHTMLAttributes } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Icon } from './Icon'
import { Spinner } from './Spinner'
import css from './IconButton.module.css'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon
  label: string
  busy?: boolean
  active?: boolean
}

export function IconButton({ icon, label, busy = false, active = false, disabled, className, ...rest }: IconButtonProps) {
  const classes = [css.iconButton, active && css.active, className].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} title={label} aria-label={label} disabled={disabled || busy} {...rest}>
      {busy ? <Spinner /> : <Icon as={icon} />}
    </button>
  )
}
