import { useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

const ENV_NAME = import.meta.env.VITE_INSTANCE_ENV_NAME as string | undefined
const IS_PROD = ENV_NAME === 'prod'

const PILL_STYLE: React.CSSProperties = {
  padding: '6px 12px',
  gap: '6px',
  height: '28px',
}

export function NavPill() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const isHome = pathname === '/'

  return (
    <>
      {!isHome && (
        <button
          onClick={() => navigate(-1)}
          className="glass-pill cursor-pointer"
          style={{ ...PILL_STYLE, gap: '4px' }}
        >
          <ArrowLeft size={12} style={{ color: 'var(--tm)' }} />
          <span style={{ fontSize: '11px', color: 'var(--tm)' }}>Back</span>
        </button>
      )}
      <button
        onClick={() => { if (!isHome) navigate('/') }}
        className="glass-pill"
        style={{
          ...PILL_STYLE,
          cursor: isHome ? 'default' : 'pointer',
        }}
      >
        <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--tm)' }}>
          Anything to <span style={{ color: 'var(--accent)' }}>Anki</span>
        </span>
        {ENV_NAME && (
          <span style={{
            fontSize: '8px',
            padding: '1px 5px',
            borderRadius: '100px',
            background: IS_PROD ? 'rgba(34,197,94,0.08)' : 'rgba(255,160,0,0.06)',
            border: `0.5px solid ${IS_PROD ? 'rgba(34,197,94,0.15)' : 'rgba(255,160,0,0.12)'}`,
            color: IS_PROD ? '#22c55e' : '#ffaa33',
          }}>
            {ENV_NAME}
          </span>
        )}
      </button>
    </>
  )
}
