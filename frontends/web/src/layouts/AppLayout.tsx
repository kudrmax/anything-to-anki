import { useRef } from 'react'
import { Outlet } from 'react-router-dom'
import { AmbientBlobs } from '@/components/AmbientBlobs'
import { PageToolbar } from '@/components/PageToolbar'
import type { ToolbarSlots } from '@/components/PageToolbar'

export function AppLayout() {
  const leftRef = useRef<HTMLDivElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)
  const slots: ToolbarSlots = { left: leftRef, right: rightRef }

  return (
    <div className="flex flex-col font-sans" style={{ height: '100dvh', color: 'var(--text)' }}>
      <AmbientBlobs />
      <PageToolbar slots={slots} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Outlet context={slots} />
      </div>
    </div>
  )
}
