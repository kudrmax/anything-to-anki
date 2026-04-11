import { useTheme } from '@/lib/ThemeProvider'

/* Back layer: huge, very transparent, slow — creates depth */
const BACK_BLOBS = [
  { size: 900, color: 'rgba(10,132,255,.08)',   anim: 'blob-back-1 70s ease-in-out infinite' },
  { size: 800, color: 'rgba(74,111,165,.06)',    anim: 'blob-back-2 80s ease-in-out infinite' },
  { size: 850, color: 'rgba(191,90,242,.04)',    anim: 'blob-back-3 75s ease-in-out infinite' },
]

/* Front layer: medium, slightly brighter, faster — visible motion */
const FRONT_BLOBS = [
  { size: 500, color: 'rgba(10,132,255,.14)',    anim: 'blob-front-1 45s ease-in-out infinite' },
  { size: 450, color: 'rgba(61,139,110,.10)',    anim: 'blob-front-2 50s ease-in-out infinite' },
  { size: 400, color: 'rgba(191,90,242,.08)',    anim: 'blob-front-3 55s ease-in-out infinite' },
  { size: 350, color: 'rgba(255,159,10,.07)',    anim: 'blob-front-4 40s ease-in-out infinite' },
]

export function AmbientBlobs() {
  const { theme } = useTheme()
  if (theme !== 'liquid-glass') return null

  return (
    <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden" aria-hidden="true">
      {/* Back layer */}
      {BACK_BLOBS.map((b, i) => (
        <div key={`b${i}`} style={{
          position: 'absolute',
          width: b.size, height: b.size,
          background: `radial-gradient(circle, ${b.color} 0%, transparent 60%)`,
          filter: 'blur(100px)',
          animation: b.anim,
        }} />
      ))}
      {/* Front layer */}
      {FRONT_BLOBS.map((b, i) => (
        <div key={`f${i}`} style={{
          position: 'absolute',
          width: b.size, height: b.size,
          background: `radial-gradient(circle, ${b.color} 0%, transparent 65%)`,
          filter: 'blur(80px)',
          animation: b.anim,
        }} />
      ))}
    </div>
  )
}
