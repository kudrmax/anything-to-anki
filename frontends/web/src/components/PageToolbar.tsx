import { BackPill, CenterBrand } from './NavPill'

export function PageToolbar({ children }: { children?: React.ReactNode }) {
  return (
    <div
      className="shrink-0 flex items-center gap-1.5 flex-wrap"
      style={{ position: 'relative', minHeight: '36px' }}
    >
      <BackPill />
      <CenterBrand />
      {children}
    </div>
  )
}
