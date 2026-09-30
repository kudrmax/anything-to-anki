import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import css from './Tooltip.module.css'

interface TooltipProps {
  anchor: HTMLElement | null
  /** Точка привязки вместо элемента, в координатах окна. */
  point?: { x: number; top: number; bottom: number }
  onClose: () => void
  children: ReactNode
}

export function Tooltip({ anchor, point, onClose, children }: TooltipProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null)

  useLayoutEffect(() => {
    const box = ref.current
    if (!box) return
    const rect = anchor?.getBoundingClientRect()
    const x = point ? point.x : rect ? rect.left : 0
    const top = point ? point.top : rect ? rect.top : 0
    const bottom = point ? point.bottom : rect ? rect.bottom : 0
    const height = box.offsetHeight
    const width = box.offsetWidth
    const fitsBelow = bottom + height < window.innerHeight
    setPosition({
      x: Math.max(0, Math.min(x, window.innerWidth - width)),
      y: fitsBelow ? bottom : Math.max(0, top - height),
    })
  }, [anchor, point])

  useEffect(() => {
    const onPointerDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  const style = { '--x': `${position?.x ?? 0}px`, '--y': `${position?.y ?? 0}px` } as CSSProperties
  return createPortal(
    <div ref={ref} role="dialog" className={position ? css.tooltip : `${css.tooltip} ${css.measuring}`} style={style}>
      {children}
    </div>,
    document.body,
  )
}
