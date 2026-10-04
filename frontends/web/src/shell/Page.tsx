import type { ReactNode } from 'react'
import css from './Page.module.css'

interface PageProps {
  header: ReactNode
  aside?: ReactNode
  banner?: ReactNode
  /** Боковая колонка свёрнута: контент плавно встаёт по центру. */
  asideHidden?: boolean
  /** Широкая основная колонка. */
  wide?: boolean
  /** На телефоне страница занимает ровно экран: контент тянется на остаток высоты. */
  fit?: boolean
  children: ReactNode
}

export function Page({ header, aside, banner, asideHidden = false, wide = false, fit = false, children }: PageProps) {
  const classes = [css.page, !aside && css.solo, aside && asideHidden && css.asideHidden, wide && css.wide, fit && css.fit].filter(Boolean).join(' ')
  return (
    <div className={classes}>
      <div className={css.full}>{header}</div>
      {banner && <div className={`${css.full} ${css.banner}`}>{banner}</div>}
      <div className={css.content}>{children}</div>
      {aside && <aside className={css.aside} aria-hidden={asideHidden}><div className={css.asideInner}>{aside}</div></aside>}
    </div>
  )
}

export function Aside({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section>
      {title && <h3 className={css.asideTitle}>{title}</h3>}
      {children}
    </section>
  )
}
