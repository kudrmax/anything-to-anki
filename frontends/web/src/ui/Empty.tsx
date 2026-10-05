import type { ReactNode } from 'react'
import css from './Empty.module.css'

/** `flush` — для экранов, где строки начинаются от края страницы, без отступа под статус-точку. */
export function Empty({ children, flush = false }: { children: ReactNode; flush?: boolean }) {
  return <div className={flush ? `${css.empty} ${css.flush}` : css.empty}>{children}</div>
}
