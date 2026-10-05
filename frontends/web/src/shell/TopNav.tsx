import { useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { statsStore, useStats } from '@/hooks/useStats'
import css from './TopNav.module.css'

const ENV_NAME = import.meta.env.VITE_INSTANCE_ENV_NAME as string | undefined
const PROD_ENV = 'prod'

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
const SETTINGS: Destination = { section: 'settings', label: 'Settings', path: '/settings' }

function sectionOf(pathname: string): Section {
  if (pathname.startsWith('/export')) return 'export'
  if (pathname.startsWith('/queue')) return 'queue'
  if (pathname.startsWith('/usage')) return 'usage'
  if (pathname.startsWith('/settings') || pathname.startsWith('/calibrate')) return 'settings'
  return 'sources'
}

export function TopNav() {
  const { pathname } = useLocation()
  const current = sectionOf(pathname)
  const stats = useStats()

  useEffect(() => { void statsStore.refresh() }, [pathname])

  const badges: Partial<Record<Section, number>> = {
    export: stats?.export_pending_count,
    queue: stats?.queue_active_count,
  }

  const tab = (destination: Destination, badge?: number) => (
    <NavLink
      key={destination.section}
      to={destination.path}
      className={current === destination.section ? `${css.tab} ${css.on}` : css.tab}
      aria-current={current === destination.section ? 'page' : undefined}
    >
      {destination.label}
      {badge ? <span className={css.badge}>{badge}</span> : null}
    </NavLink>
  )

  return (
    <nav className={css.nav}>
      {MAIN.map(destination => tab(destination, badges[destination.section]))}
      <span className={css.spacer} />
      {ENV_NAME && <span className={ENV_NAME === PROD_ENV ? `${css.env} ${css.prod}` : css.env}>{ENV_NAME}</span>}
      {tab(SETTINGS)}
    </nav>
  )
}
