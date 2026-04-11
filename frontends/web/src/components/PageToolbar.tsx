import { BackPill, CenterBrand } from './NavPill'
import { FONT_MENU } from '@/lib/design-tokens'

export const TOOLBAR_SPACING = '12px'
export const TOOLBAR_HEIGHT = '56px'

export interface ToolbarSlots {
  left: React.RefObject<HTMLDivElement | null>
  right: React.RefObject<HTMLDivElement | null>
}

export function PageToolbar({ slots }: { slots: ToolbarSlots }) {
  return (
    <div
      className="shrink-0 flex items-center gap-1.5"
      style={{
        height: TOOLBAR_HEIGHT,
        fontSize: FONT_MENU,
        padding: `0 ${TOOLBAR_SPACING}`,
      }}
    >
      {/* Left zone: Back + left page pills */}
      <div className="flex items-center gap-1.5" style={{ flex: 1, minWidth: 0 }}>
        <BackPill />
        <div ref={slots.left} className="contents" />
      </div>

      {/* Center zone: Anki + Settings — always centered */}
      <CenterBrand />

      {/* Right zone: right page pills */}
      <div className="flex items-center gap-1.5 justify-end" style={{ flex: 1, minWidth: 0 }}>
        <div ref={slots.right} className="contents" />
      </div>
    </div>
  )
}
