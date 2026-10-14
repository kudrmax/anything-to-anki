import { useRef, type TouchEvent } from 'react'

export type SwipeDirection = 'left' | 'right'

/** Сдвиг пальца, после которого жест считается свайпом, а не тапом. */
const MIN_DISTANCE_PX = 60
/** Во сколько раз горизонтальный сдвиг должен превышать вертикальный: иначе это прокрутка карточки. */
const HORIZONTAL_RATIO = 1.5

interface SwipeHandlers {
  onTouchStart: (e: TouchEvent) => void
  onTouchEnd: (e: TouchEvent) => void
}

/** Горизонтальный свайп одним пальцем; вертикальная прокрутка и тапы его не вызывают. */
export function useSwipe(onSwipe: (direction: SwipeDirection) => void): SwipeHandlers {
  const start = useRef<{ x: number; y: number } | null>(null)
  return {
    onTouchStart: e => {
      const touch = e.touches[0]
      start.current = e.touches.length === 1 && touch ? { x: touch.clientX, y: touch.clientY } : null
    },
    onTouchEnd: e => {
      const from = start.current
      start.current = null
      const touch = e.changedTouches[0]
      if (!from || !touch) return
      const dx = touch.clientX - from.x
      const dy = touch.clientY - from.y
      if (Math.abs(dx) < MIN_DISTANCE_PX || Math.abs(dx) < Math.abs(dy) * HORIZONTAL_RATIO) return
      onSwipe(dx < 0 ? 'left' : 'right')
    },
  }
}
