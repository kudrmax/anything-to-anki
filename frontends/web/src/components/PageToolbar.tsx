import { BackPill, CenterBrand } from './NavPill'

export const TOOLBAR_SPACING = '12px'
export const TOOLBAR_FONT_SIZE = '10px'

export function PageToolbar({ children }: { children?: React.ReactNode }) {
  return (
    <div
      className="shrink-0 flex items-center gap-1.5 flex-wrap"
      style={{
        position: 'relative',
        minHeight: '28px',
        margin: TOOLBAR_SPACING,
        fontSize: TOOLBAR_FONT_SIZE,
      }}
    >
      <BackPill />
      <CenterBrand />
      {children}
    </div>
  )
}
