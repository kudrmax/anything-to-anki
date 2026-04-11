import { BackPill, CenterBrand } from './NavPill'
import { FONT_MENU } from '@/lib/design-tokens'

export const TOOLBAR_SPACING = '12px'
export const TOOLBAR_HEIGHT = '56px'

export function PageToolbar({ slotRef }: { slotRef: React.RefObject<HTMLDivElement | null> }) {
  return (
    <div
      className="shrink-0 flex items-center gap-1.5"
      style={{
        height: TOOLBAR_HEIGHT,
        fontSize: FONT_MENU,
        padding: `0 ${TOOLBAR_SPACING}`,
      }}
    >
      <BackPill />
      <CenterBrand />
      <div ref={slotRef} className="contents" />
    </div>
  )
}
