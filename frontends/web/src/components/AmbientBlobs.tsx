import { useLocation } from 'react-router-dom'
import { useTheme } from '@/lib/ThemeProvider'

/* Back layer: huge, very transparent, slow — creates depth.
   Sizes are large + gradient fades early to simulate soft blur without filter:blur(). */
const BACK_BLOBS = [
  { size: 1300, color: 'rgba(10,132,255,.035)',  anim: 'blob-back-1 70s ease-in-out infinite' },
  { size: 1200, color: 'rgba(74,111,165,.04)',   anim: 'blob-back-2 80s ease-in-out infinite' },
  { size: 1250, color: 'rgba(191,90,242,.03)',   anim: 'blob-back-3 75s ease-in-out infinite' },
]

/* Front layer: medium, slightly brighter, faster — visible motion */
const FRONT_BLOBS = [
  { size: 800, color: 'rgba(10,132,255,.06)',    anim: 'blob-front-1 45s ease-in-out infinite' },
  { size: 750, color: 'rgba(61,139,110,.07)',    anim: 'blob-front-2 50s ease-in-out infinite' },
  { size: 700, color: 'rgba(191,90,242,.055)',   anim: 'blob-front-3 55s ease-in-out infinite' },
  { size: 650, color: 'rgba(255,159,10,.05)',    anim: 'blob-front-4 40s ease-in-out infinite' },
]

export function AmbientBlobs() {
  const { theme } = useTheme()
  const { pathname } = useLocation()
  if (theme !== 'liquid-glass') return null
  if (pathname.includes('/review')) return null

  return (
    <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden" aria-hidden="true">
      {/* Back layer */}
      {BACK_BLOBS.map((b, i) => (
        <div key={`b${i}`} style={{
          position: 'absolute',
          width: b.size, height: b.size,
          background: `radial-gradient(circle, ${b.color} 0%, transparent 40%)`,
          willChange: 'transform',
          animation: b.anim,
        }} />
      ))}
      {/* Front layer */}
      {FRONT_BLOBS.map((b, i) => (
        <div key={`f${i}`} style={{
          position: 'absolute',
          width: b.size, height: b.size,
          background: `radial-gradient(circle, ${b.color} 0%, transparent 45%)`,
          willChange: 'transform',
          animation: b.anim,
        }} />
      ))}
    </div>
  )
}
