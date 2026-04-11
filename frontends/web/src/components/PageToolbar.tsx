import { BackPill, CenterBrand } from './NavPill'
import { FONT_MENU } from '@/lib/design-tokens'

export const TOOLBAR_SPACING = '12px'

export function PageToolbar({ slotRef }: { slotRef: React.RefObject<HTMLDivElement | null> }) {
  return (
    <div
      className="shrink-0 flex items-center gap-1.5 flex-wrap"
      style={{
        position: 'relative',
        height: '56px',
        fontSize: FONT_MENU,
        padding: TOOLBAR_SPACING,
      }}
    >
      <BackPill />
      <CenterBrand />
      {/* Page-specific pills get portaled here */}
      <div ref={slotRef} className="contents" />
    </div>
  )
}
