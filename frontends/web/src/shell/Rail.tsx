import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Inbox, Layers, Settings, Upload, type LucideIcon } from 'lucide-react'
import { api } from '@/api/client'
import { IconButton } from '@/ui'
import css from './Rail.module.css'

const ENV_NAME = import.meta.env.VITE_INSTANCE_ENV_NAME as string | undefined
const PROD_ENV = 'prod'

type Section = 'sources' | 'export' | 'queue' | 'settings'

interface Destination {
  section: Section
  label: string
  path: string
  icon: LucideIcon
}

const MAIN: Destination[] = [
  { section: 'sources', label: 'Sources', path: '/', icon: Inbox },
  { section: 'export', label: 'Export', path: '/export', icon: Upload },
  { section: 'queue', label: 'Queue', path: '/queue', icon: Layers },
]
const SETTINGS: Destination = { section: 'settings', label: 'Settings', path: '/settings', icon: Settings }

function sectionOf(pathname: string): Section {
  if (pathname.startsWith('/export')) return 'export'
  if (pathname.startsWith('/queue')) return 'queue'
  if (pathname.startsWith('/settings') || pathname.startsWith('/calibrate')) return 'settings'
  return 'sources'
}

export function Rail() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const current = sectionOf(pathname)
  const [learnCount, setLearnCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    api.getStats().then(stats => { if (!cancelled) setLearnCount(stats.learn_count) }).catch(() => {})
    return () => { cancelled = true }
  }, [pathname])

  const item = (destination: Destination, badge?: number) => (
    <span key={destination.section} className={css.item}>
      <IconButton
        icon={destination.icon}
        label={destination.label}
        active={current === destination.section}
        onClick={() => navigate(destination.path)}
      />
      {badge ? <sup className={css.badge}>{badge}</sup> : null}
    </span>
  )

  return (
    <nav className={css.rail}>
      <div className={css.logo}>Aa</div>
      {ENV_NAME && <div className={ENV_NAME === PROD_ENV ? `${css.env} ${css.prod}` : css.env}>{ENV_NAME}</div>}
      {MAIN.map(destination => item(destination, destination.section === 'export' ? learnCount : undefined))}
      <span className={css.spacer} />
      {item(SETTINGS)}
    </nav>
  )
}
