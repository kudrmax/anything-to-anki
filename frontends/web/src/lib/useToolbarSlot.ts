import { useOutletContext } from 'react-router-dom'
import type { ToolbarSlots } from '@/components/PageToolbar'

/** Returns refs to toolbar left/right slot containers for portaling page-specific pills */
export function useToolbarSlots(): ToolbarSlots {
  return useOutletContext<ToolbarSlots>()
}
