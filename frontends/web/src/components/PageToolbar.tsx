import { BackPill, CenterBrand } from './NavPill'

const TOOLBAR_PADDING = '12px'

export function PageToolbar({ children }: { children?: React.ReactNode }) {
  return (
    <div
      className="shrink-0 flex items-center gap-1.5 flex-wrap"
      style={{
        position: 'relative',
        minHeight: '28px',
        padding: `${TOOLBAR_PADDING} ${TOOLBAR_PADDING} ${TOOLBAR_PADDING} ${TOOLBAR_PADDING}`,
      }}
    >
      <BackPill />
      <CenterBrand />
      {children}
    </div>
  )
}
