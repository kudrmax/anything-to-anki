import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { IconButton } from './IconButton'
import css from './Banner.module.css'

interface BannerProps {
  tone: 'warn' | 'err'
  onDismiss?: () => void
  children: ReactNode
}

export function Banner({ tone, onDismiss, children }: BannerProps) {
  return (
    <div className={`${css.banner} ${css[tone]}`} role="alert">
      <div className={css.text}>{children}</div>
      {onDismiss && <IconButton icon={X} label="Dismiss" onClick={onDismiss} />}
    </div>
  )
}
