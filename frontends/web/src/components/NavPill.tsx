import { useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft, Download, Settings } from 'lucide-react'

const ENV_NAME = import.meta.env.VITE_INSTANCE_ENV_NAME as string | undefined
const IS_PROD = ENV_NAME === 'prod'

/** Back pill — in flow, only on non-home pages */
export function BackPill() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  if (pathname === '/') return null

  return (
    <button
      onClick={() => navigate(-1)}
      className="glass-pill cursor-pointer"
      style={{ gap: '4px' }}
    >
      <ArrowLeft size={12} style={{ color: 'var(--tm)' }} />
      <span style={{ color: 'var(--tm)' }}>Back</span>
    </button>
  )
}

/** "Anything to Anki" + Settings — in flow, centered via spacers from PageToolbar */
export function CenterBrand() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const isHome = pathname === '/'
  const isSettings = pathname === '/settings'
  const isExport = pathname === '/export'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
      <button
        onClick={() => { if (!isHome) navigate('/') }}
        className="glass-pill"
        style={{
          gap: '6px',
          cursor: isHome ? 'default' : 'pointer',
        }}
      >
        <span style={{ fontWeight: 500, color: 'var(--tm)' }}>
          Anything to <span style={{ color: 'var(--accent)' }}>Anki</span>
        </span>
        {ENV_NAME && (
          <span
            className="glass-pill"
            style={{
              fontSize: '8px',
              padding: '1px 5px',
              height: 'auto',
              background: IS_PROD ? 'var(--status-learn-bg)' : 'rgba(255,160,0,0.06)',
              borderColor: IS_PROD ? 'var(--status-learn-border)' : 'rgba(255,160,0,0.12)',
              color: IS_PROD ? 'var(--status-learn)' : '#ffaa33',
            }}
          >
            {ENV_NAME}
          </span>
        )}
      </button>
      {!isExport && (
        <button
          onClick={() => navigate('/export')}
          className="glass-pill cursor-pointer"
        >
          <Download size={12} style={{ color: 'var(--td)' }} />
        </button>
      )}
      {!isSettings && (
        <button
          onClick={() => navigate('/settings')}
          className="glass-pill cursor-pointer"
        >
          <Settings size={12} style={{ color: 'var(--td)' }} />
        </button>
      )}
    </div>
  )
}
