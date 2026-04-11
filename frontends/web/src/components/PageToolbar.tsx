import { NavPill } from './NavPill'

export function PageToolbar({ children }: { children?: React.ReactNode }) {
  return (
    <div className="shrink-0 flex flex-col gap-1.5">
      <NavPill />
      {children && (
        <div className="flex items-center gap-1.5 flex-wrap">
          {children}
        </div>
      )}
    </div>
  )
}
