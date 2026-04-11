import { useTheme } from '@/lib/ThemeProvider'

export function AmbientBlobs() {
  const { theme } = useTheme()
  if (theme !== 'liquid-glass') return null

  return (
    <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden" aria-hidden="true">
      <div style={{
        position: 'absolute', width: 500, height: 500,
        top: '-10%', left: '-5%',
        background: 'radial-gradient(circle, rgba(10,132,255,.15) 0%, transparent 65%)',
        filter: 'blur(80px)',
      }} />
      <div style={{
        position: 'absolute', width: 420, height: 420,
        bottom: '-10%', right: '-5%',
        background: 'radial-gradient(circle, rgba(48,209,88,.09) 0%, transparent 65%)',
        filter: 'blur(80px)',
      }} />
      <div style={{
        position: 'absolute', width: 320, height: 320,
        top: '35%', left: '50%',
        background: 'radial-gradient(circle, rgba(191,90,242,.07) 0%, transparent 65%)',
        filter: 'blur(70px)',
      }} />
      <div style={{
        position: 'absolute', width: 260, height: 260,
        top: '5%', right: '15%',
        background: 'radial-gradient(circle, rgba(255,159,10,.05) 0%, transparent 65%)',
        filter: 'blur(70px)',
      }} />
    </div>
  )
}
