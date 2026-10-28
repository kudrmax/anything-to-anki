import { useCallback, useState, type PointerEvent as ReactPointerEvent } from 'react'

/** Окно поверх экрана: тянется за заголовок, где его оставили — там и стоит. */
export function useFloatingWindow() {
  const [offset, setOffset] = useState({ x: 0, y: 0 })

  const startMove = useCallback((e: ReactPointerEvent) => {
    if (e.button !== 0 || (e.target instanceof Element && e.target.closest('button'))) return
    e.preventDefault()
    const from = { x: e.clientX - offset.x, y: e.clientY - offset.y }
    const move = (ev: PointerEvent) => setOffset({ x: ev.clientX - from.x, y: ev.clientY - from.y })
    const stop = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
  }, [offset])

  return { offset, startMove }
}
