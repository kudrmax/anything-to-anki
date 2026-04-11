import { BackPill, CenterBrand } from './NavPill'
import { FONT_MENU } from '@/lib/design-tokens'

export const TOOLBAR_SPACING = '12px'

export function PageToolbar({ children }: { children?: React.ReactNode }) {
  return (
    <div
      className="shrink-0 flex items-center gap-1.5 flex-wrap"
      style={{
        position: 'relative',
        minHeight: '32px',
        fontSize: FONT_MENU,
        padding: TOOLBAR_SPACING,
      }}
    >
      <BackPill />
      <CenterBrand />
      {children}
    </div>
  )
}
