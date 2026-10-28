import { useCallback, useState, type PointerEvent as ReactPointerEvent, type RefObject } from 'react'
import { findTarget, type DragItem, type DropTarget } from './layoutDrag'

/** Пока указатель сдвинулся меньше, это щелчок, а не перетаскивание. */
const DRAG_THRESHOLD = 4

export interface LayoutDrag {
  item: DragItem
  x: number
  y: number
  target: DropTarget | null
}

/**
 * Перетаскивание указателем — мышью и пальцем одинаково. Щелчок без сдвига — onClick,
 * бросок — onDrop с местом, куда отпустили.
 */
export function useLayoutDrag(
  rootRef: RefObject<HTMLElement | null>,
  onDrop: (item: DragItem, target: DropTarget) => void,
  onClick: (item: DragItem) => void,
) {
  const [drag, setDrag] = useState<LayoutDrag | null>(null)

  const start = useCallback((item: DragItem) => (e: ReactPointerEvent) => {
    if (e.button !== 0) return
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startY = e.clientY
    let dragging = false
    let target: DropTarget | null = null

    const move = (ev: PointerEvent) => {
      if (!dragging && Math.hypot(ev.clientX - startX, ev.clientY - startY) < DRAG_THRESHOLD) return
      dragging = true
      target = rootRef.current ? findTarget(rootRef.current, item, ev.clientX, ev.clientY) : null
      setDrag({ item, x: ev.clientX, y: ev.clientY, target })
    }
    const stop = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', stop)
      setDrag(null)
    }
    const up = () => {
      stop()
      if (!dragging) onClick(item)
      else if (target) onDrop(item, target)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', stop)
  }, [rootRef, onDrop, onClick])

  return { drag, start }
}
