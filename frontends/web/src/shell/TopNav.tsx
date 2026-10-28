import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { Settings } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'
import { statsStore, useStats } from '@/hooks/useStats'
import { windowTitlebar } from '@/lib/nativeHost'
import { Icon } from '@/ui'
import { UpdateIndicator } from './updates/UpdateIndicator'
import { useUpdates } from './updates/useUpdates'
import css from './TopNav.module.css'

const ENV_NAME = import.meta.env.VITE_INSTANCE_ENV_NAME as string | undefined
const PROD_ENV = 'prod'
export const SETTINGS_PATH = '/settings'
/** Редактор раскладки карточки открывается из настроек и относится к ним. */
export const CARD_LAYOUT_PATH = '/card-layout'

type Section = 'sources' | 'export' | 'queue' | 'usage' | 'settings'

interface Destination {
  section: Section
  label: string
  path: string
}

const MAIN: Destination[] = [
  { section: 'sources', label: 'Sources', path: '/' },
  { section: 'export', label: 'Export', path: '/export' },
  { section: 'queue', label: 'Queue', path: '/queue' },
  { section: 'usage', label: 'Usage', path: '/usage' },
]
const SETTINGS: Destination = { section: 'settings', label: 'Settings', path: SETTINGS_PATH }
const CONTROL = 'a, button, input, [role="button"]'
const PRIMARY_BUTTON = 0
const DOUBLE_CLICK = 2

function sectionOf(pathname: string): Section {
  if (pathname.startsWith('/export')) return 'export'
  if (pathname.startsWith('/queue')) return 'queue'
  if (pathname.startsWith('/usage')) return 'usage'
  if (pathname.startsWith(SETTINGS_PATH) || pathname.startsWith(CARD_LAYOUT_PATH) || pathname.startsWith('/calibrate')) return 'settings'
  return 'sources'
}

export function TopNav() {
  const { pathname } = useLocation()
  const current = sectionOf(pathname)
  const stats = useStats()
  const updateAvailable = useUpdates().status?.available === true
  const main = useRef<HTMLDivElement>(null)
  const [titlebar] = useState(() => windowTitlebar())

  useEffect(() => { void statsStore.refresh() }, [pathname])

  const badges: Partial<Record<Section, number>> = {
    export: stats?.export_pending_count,
    queue: stats?.queue_active_count,
  }

  // Вкладки, которые не влезли, прокручиваются: открытая не должна оставаться за краем.
  useEffect(() => {
    main.current?.querySelector('[data-current]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [current, badges.export, badges.queue])

  const tab = (destination: Destination, badge?: number) => (
    <NavLink
      key={destination.section}
      to={destination.path}
      className={current === destination.section ? `${css.tab} ${css.on}` : css.tab}
      aria-current={current === destination.section ? 'page' : undefined}
      data-current={current === destination.section || undefined}
    >
      {destination.label}
      {badge ? <span className={css.badge}>{badge}</span> : null}
    </NavLink>
  )

  // В приложении для macOS шапка лежит на месте заголовка окна: её пустое место двигает окно.
  const onMouseDown = (event: MouseEvent) => {
    if (!titlebar || event.button !== PRIMARY_BUTTON) return
    if (event.target instanceof Element && event.target.closest(CONTROL)) return
    if (event.detail === DOUBLE_CLICK) titlebar.doubleClick()
    else titlebar.drag()
  }

  const on = current === SETTINGS.section
  return (
    <nav className={css.nav} onMouseDown={onMouseDown}>
      <div ref={main} className={css.main}>
        {MAIN.map(destination => tab(destination, badges[destination.section]))}
        <span className={css.spacer} />
      </div>
      <div className={css.end}>
        <UpdateIndicator />
        {ENV_NAME && <span className={ENV_NAME === PROD_ENV ? `${css.env} ${css.prod}` : css.env}>{ENV_NAME}</span>}
        <NavLink
          to={SETTINGS.path}
          className={on ? `${css.tab} ${css.on}` : css.tab}
          aria-current={on ? 'page' : undefined}
          aria-label={SETTINGS.label}
          data-current={on || undefined}
        >
          <span className={css.label}>{SETTINGS.label}</span>
          <span className={css.icon}><Icon as={Settings} /></span>
          {updateAvailable && <span className={css.updateDot} />}
        </NavLink>
      </div>
    </nav>
  )
}
