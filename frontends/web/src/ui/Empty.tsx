import type { ReactNode } from 'react'
import css from './Empty.module.css'

export function Empty({ children }: { children: ReactNode }) {
  return <div className={css.empty}>{children}</div>
}
