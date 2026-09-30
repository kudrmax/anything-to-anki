import type { ReactNode } from 'react'
import css from './Text.module.css'

interface TextProps {
  tone?: 'default' | 'soft' | 'muted' | 'accent' | 'ok' | 'warn' | 'err'
  size?: 's' | 'm'
  mono?: boolean
  block?: boolean
  children: ReactNode
}

export function Text({ tone = 'default', size, mono = false, block = false, children }: TextProps) {
  const classes = [css[tone], size && css[size], mono && css.mono, block && css.block].filter(Boolean).join(' ')
  return <span className={classes}>{children}</span>
}

export function Label({ children, flush = false }: { children: ReactNode; flush?: boolean }) {
  return <div className={flush ? `${css.label} ${css.flush}` : css.label}>{children}</div>
}
