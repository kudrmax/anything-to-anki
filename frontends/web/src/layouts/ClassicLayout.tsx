import { useRef } from 'react'
import { Outlet } from 'react-router-dom'
import { AmbientBlobs } from '@/components/AmbientBlobs'
import { PageToolbar } from '@/components/PageToolbar'

export function ClassicLayout() {
  const toolbarSlotRef = useRef<HTMLDivElement>(null)

  return (
    <div className="flex flex-col font-sans" style={{ height: '100dvh', color: 'var(--text)' }}>
      <AmbientBlobs />
      <PageToolbar slotRef={toolbarSlotRef} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Outlet context={toolbarSlotRef} />
      </div>
    </div>
  )
}
