import { useTheme } from '@/lib/ThemeProvider'

const BLOBS = [
  {
    size: 500,
    color: 'rgba(10,132,255,.15)',
    animation: 'blob-drift-1 45s ease-in-out infinite',
  },
  {
    size: 420,
    color: 'rgba(48,209,88,.09)',
    animation: 'blob-drift-2 55s ease-in-out infinite',
  },
  {
    size: 320,
    color: 'rgba(191,90,242,.07)',
    animation: 'blob-drift-3 50s ease-in-out infinite',
  },
  {
    size: 260,
    color: 'rgba(255,159,10,.05)',
    animation: 'blob-drift-4 40s ease-in-out infinite',
  },
]

export function AmbientBlobs() {
  const { theme } = useTheme()
  if (theme !== 'liquid-glass') return null

  return (
    <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden" aria-hidden="true">
      {BLOBS.map((blob, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            width: blob.size,
            height: blob.size,
            background: `radial-gradient(circle, ${blob.color} 0%, transparent 65%)`,
            filter: 'blur(80px)',
            animation: blob.animation,
          }}
        />
      ))}
    </div>
  )
}
