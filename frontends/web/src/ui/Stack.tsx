import type { ReactNode } from 'react'
import css from './Stack.module.css'

interface StackProps {
  gap?: 'xs' | 's' | 'm' | 'l'
  row?: boolean
  wrap?: boolean
  children: ReactNode
}

export function Stack({ gap = 's', row = false, wrap = false, children }: StackProps) {
  const classes = [css.stack, css[gap], row && css.row, wrap && css.wrap].filter(Boolean).join(' ')
  return <div className={classes}>{children}</div>
}
