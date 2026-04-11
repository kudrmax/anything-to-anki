import { useNavigate, useLocation } from 'react-router-dom'

export function NavPill() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const isHome = pathname === '/'

  return (
    <button
      onClick={() => { if (!isHome) navigate('/') }}
      className="glass-pill"
      style={{
        padding: '5px 10px',
        gap: '6px',
        cursor: isHome ? 'default' : 'pointer',
      }}
    >
      {!isHome && (
        <span style={{ color: 'var(--tm)', fontSize: '14px' }}>‹</span>
      )}
      <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--tm)' }}>
        Anything to <span style={{ color: 'var(--accent)' }}>Anki</span>
      </span>
      {import.meta.env.VITE_INSTANCE_ENV_NAME && (
        <span style={{
          fontSize: '8px',
          padding: '1px 5px',
          borderRadius: '100px',
          background: import.meta.env.VITE_INSTANCE_ENV_NAME === 'prod' ? 'rgba(34,197,94,0.08)' : 'rgba(255,160,0,0.06)',
          border: `0.5px solid ${import.meta.env.VITE_INSTANCE_ENV_NAME === 'prod' ? 'rgba(34,197,94,0.15)' : 'rgba(255,160,0,0.12)'}`,
          color: import.meta.env.VITE_INSTANCE_ENV_NAME === 'prod' ? '#22c55e' : '#ffaa33',
        }}>
          {import.meta.env.VITE_INSTANCE_ENV_NAME}
        </span>
      )}
    </button>
  )
}
