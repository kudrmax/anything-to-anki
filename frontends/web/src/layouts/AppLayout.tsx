import { ClassicLayout } from './ClassicLayout'
import { SidebarLayout } from './SidebarLayout'

const layout = (import.meta.env.VITE_LAYOUT ?? 'classic') as 'classic' | 'sidebar'

export function AppLayout() {
  return layout === 'sidebar' ? <SidebarLayout /> : <ClassicLayout />
}
