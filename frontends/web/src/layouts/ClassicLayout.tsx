import { Outlet } from 'react-router-dom'
import { AmbientBlobs } from '@/components/AmbientBlobs'

export function ClassicLayout() {
  return (
    <div className="flex flex-col font-sans" style={{ height: '100dvh', color: 'var(--text)' }}>
      <AmbientBlobs />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </div>
    </div>
  )
}
