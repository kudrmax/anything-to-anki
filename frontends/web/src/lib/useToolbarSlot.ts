import { useOutletContext } from 'react-router-dom'
import type { RefObject } from 'react'

/** Returns the ref to the toolbar slot container for portaling page-specific pills */
export function useToolbarSlot(): RefObject<HTMLDivElement | null> {
  return useOutletContext<RefObject<HTMLDivElement | null>>()
}
