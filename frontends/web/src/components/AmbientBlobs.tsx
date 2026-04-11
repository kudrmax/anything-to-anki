import { useTheme } from '@/lib/ThemeProvider'

export function AmbientBlobs() {
  const { theme } = useTheme()
  if (theme !== 'liquid-glass') return null

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 0 }} aria-hidden="true">
      <div style={{
        position: 'absolute', width: 600, height: 600,
        top: '-15%', left: '-10%',
        background: 'radial-gradient(circle, rgba(10,132,255,.22) 0%, transparent 60%)',
        filter: 'blur(90px)',
      }} />
      <div style={{
        position: 'absolute', width: 500, height: 500,
        bottom: '-12%', right: '-8%',
        background: 'radial-gradient(circle, rgba(48,209,88,.13) 0%, transparent 60%)',
        filter: 'blur(90px)',
      }} />
      <div style={{
        position: 'absolute', width: 400, height: 400,
        top: '30%', left: '45%',
        background: 'radial-gradient(circle, rgba(191,90,242,.1) 0%, transparent 60%)',
        filter: 'blur(80px)',
      }} />
      <div style={{
        position: 'absolute', width: 350, height: 350,
        top: '5%', right: '10%',
        background: 'radial-gradient(circle, rgba(255,159,10,.08) 0%, transparent 60%)',
        filter: 'blur(80px)',
      }} />
      <div style={{
        position: 'absolute', width: 450, height: 450,
        bottom: '15%', left: '25%',
        background: 'radial-gradient(circle, rgba(94,230,255,.06) 0%, transparent 55%)',
        filter: 'blur(100px)',
      }} />
    </div>
  )
}
