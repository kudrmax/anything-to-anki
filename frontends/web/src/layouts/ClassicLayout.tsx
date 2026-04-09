import { Outlet, useNavigate } from 'react-router-dom'
import { Settings } from 'lucide-react'

export function ClassicLayout() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col font-sans" style={{ height: '100dvh', color: 'var(--text)' }}>
      <header
        className="shrink-0 flex items-center justify-between px-6"
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
        <button
          onClick={() => navigate('/')}
          className="text-lg font-bold cursor-pointer"
          style={{ letterSpacing: '-0.4px', color: 'var(--text)' }}
        >
          <span className="flex items-center gap-2">
            <img src="/anki-logo.png" alt="Anki" className="w-7 h-7 rounded-lg object-cover" />
            Anything to <span className="grad-text">Anki</span>
            {import.meta.env.VITE_INSTANCE_ENV_NAME && (
              <span style={{
                fontSize: '10px',
                fontWeight: 600,
                letterSpacing: '0.05em',
                padding: '1px 6px',
                borderRadius: '4px',
                background: 'rgba(255,160,0,0.15)',
                color: '#ffaa33',
                border: '1px solid rgba(255,160,0,0.3)',
                lineHeight: '16px',
              }}>
                {import.meta.env.VITE_INSTANCE_ENV_NAME}
              </span>
            )}
          </span>
        </button>
        <button
          onClick={() => navigate('/settings')}
          className="p-2 cursor-pointer transition-opacity hover:opacity-100"
          style={{ color: 'var(--tm)', opacity: 0.7 }}
          aria-label="Settings"
        >
          <Settings size={16} />
        </button>
      </header>

      <div className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </div>
    </div>
  )
}
