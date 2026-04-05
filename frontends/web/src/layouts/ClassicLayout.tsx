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
          Vocab<span className="grad-text">Miner</span>
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
