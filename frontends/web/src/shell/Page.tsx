import { useEffect, useRef, type ReactNode } from 'react'
import { useStats } from '@/hooks/useStats'
import { AIOutageBanner } from './AIOutageBanner'
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
  /** Без боковой колонки контент всё равно занимает всю ширину окна: экран сам делит её на колонки. */
  fill?: boolean
  /** На телефоне экран занимает всё окно: вкладки приложения прячутся, назад ведёт стрелка шапки. */
  immersive?: boolean
  /** Шапка держится сверху при прокрутке окна. */
  stickyHeader?: boolean
  children: ReactNode
}

export function Page({ header, aside, banner, asideHidden = false, wide = false, fit = false, fill = false, immersive = false, stickyHeader = false, children }: PageProps) {
  const aiUnavailable = useStats()?.ai_unavailable
  const pageRef = useRef<HTMLDivElement>(null)
  const headRef = useRef<HTMLDivElement>(null)
  // Боковая колонка прилипает под шапкой, а высота шапки зависит от переноса заголовка.
  useEffect(() => {
    const page = pageRef.current
    const head = headRef.current
    if (!stickyHeader || !page || !head) return
    const measure = () => page.style.setProperty('--page-head-h', `${head.offsetHeight}px`)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(head)
    return () => observer.disconnect()
  }, [stickyHeader])
  const classes = [css.page, !aside && css.solo, aside && asideHidden && css.asideHidden, wide && css.wide, fit && css.fit, fill && css.fill, stickyHeader && css.stickyHeader].filter(Boolean).join(' ')
  return (
    <div ref={pageRef} className={classes} data-immersive={immersive || undefined}>
      <div ref={headRef} className={css.full}>{header}</div>
      {(aiUnavailable || banner) && (
        <div className={`${css.full} ${css.banner}`}>
          {aiUnavailable && <AIOutageBanner reason={aiUnavailable} />}
          {banner}
        </div>
      )}
      <div className={css.content}>{children}</div>
      {aside && <aside className={css.aside} aria-hidden={asideHidden}><div className={css.asideInner}>{aside}</div></aside>}
    </div>
  )
}

export function Aside({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className={css.asideSection}>
      {title && <h3 className={css.asideTitle}>{title}</h3>}
      {children}
    </section>
  )
}
