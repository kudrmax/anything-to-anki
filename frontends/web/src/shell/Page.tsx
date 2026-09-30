import type { ReactNode } from 'react'
import css from './Page.module.css'

interface PageProps {
  header: ReactNode
  aside?: ReactNode
  banner?: ReactNode
  children: ReactNode
}

export function Page({ header, aside, banner, children }: PageProps) {
  return (
    <div className={css.page}>
      <div className={css.full}>{header}</div>
      {banner && <div className={`${css.full} ${css.banner}`}>{banner}</div>}
      <div className={css.content}>{children}</div>
      {aside && <aside className={css.aside}>{aside}</aside>}
    </div>
  )
}

export function Aside({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className={css.asideTitle}>{title}</h3>
      {children}
    </section>
  )
}
