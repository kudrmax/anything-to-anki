import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { LayoutDashboard, Settings } from 'lucide-react'

const NAV = [
  { icon: LayoutDashboard, label: 'Inbox', path: '/' },
  { icon: Settings,        label: 'Settings', path: '/settings' },
] as const

export function SidebarLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  function isActive(path: string) {
    if (path === '/') return pathname === '/'
    return pathname.startsWith(path)
  }

  return (
    <div className="flex flex-col font-sans" style={{ height: '100dvh', color: 'var(--text)' }}>
      {/* App header */}
      <header
        className="shrink-0 flex items-center px-6"
        style={{
          height: 'var(--header-h)',
          background: 'var(--header-bg)',
          backdropFilter: 'blur(28px) saturate(180%)',
          WebkitBackdropFilter: 'blur(28px) saturate(180%)',
          borderBottom: '1px solid var(--glass-b)',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div className="text-lg font-bold" style={{ letterSpacing: '-0.4px' }}>
          Vocab<span className="grad-text">Miner</span>
        </div>
      </header>

      {/* Shell */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside
          className="shrink-0 flex flex-col gap-1 px-3 py-4 overflow-y-auto"
          style={{
            width: '220px',
            background: 'rgba(12,14,24,.72)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            borderRight: '1px solid var(--glass-b)',
          }}
        >
          {NAV.map(({ icon: Icon, label, path }) => (
            <button
              key={path}
              onClick={() => navigate(path)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium cursor-pointer w-full text-left transition-all"
              style={{
                color:      isActive(path) ? 'var(--accent)' : 'var(--tm)',
                background: isActive(path) ? 'var(--abg)'   : 'transparent',
                boxShadow:  isActive(path) ? 'inset 0 0 0 1px var(--ag)' : 'none',
              }}
            >
              <Icon size={15} style={{ opacity: isActive(path) ? 1 : 0.65 }} />
              {label}
            </button>
          ))}
        </aside>

        {/* Page content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
