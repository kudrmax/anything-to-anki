import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { dragDirection, dragProgress, releasedDirection, swipeAxis, type CardSize, type Offset, type SwipeDirection, type Velocity } from './swipeDecision'

interface DecisionSwipeOptions {
  enabled: boolean
  /** Свайп вниз: только пока карточка не прокручивается — иначе вертикаль отдана прокрутке. */
  vertical: boolean
  /** Можно ли решить в эту сторону; нельзя — карточка возвращается на место. */
  canSwipe: (direction: SwipeDirection) => boolean
  onSwipe: (direction: SwipeDirection) => Promise<void>
}

/** Что делает карточка: едет за пальцем, улетает или возвращается. Нет атрибута — стоит на месте. */
export const DRAG_ATTR = 'data-drag'
/** Куда тянут карточку: по нему проступает метка решения. */
export const SWIPE_ATTR = 'data-swipe'
type DragState = 'move' | 'fly' | 'back'

/** Сколько длится вылет карточки и её возврат; то же время — у перехода в CSS. */
const ANIMATION_MS = 200
/** Окно, по которому считается скорость пальца в момент отпускания. */
const SPEED_WINDOW_MS = 100
/** Наклон карточки на каждый пиксель сдвига вбок. */
const TILT_DEG_PER_PX = 0.05
/** Вылетая, карточка уходит на полторы своих ширины (вбок) или высоты (вниз). */
const FLY_DISTANCE = 1.5
/** Поля ввода жест не перехватывает: там выделяют и правят текст. */
const TEXT_INPUT = 'input, textarea, [contenteditable="true"]'

interface Gesture {
  pointerId: number
  x: number
  y: number
  /** Палец ушёл дальше тапа: карточка едет за ним. */
  dragging: boolean
  samples: { t: number; x: number; y: number }[]
}

/**
 * Свайп решения, как в Tinder: карточка свободно едет за пальцем или мышью, дотянутая или брошенная — улетает
 * туда, куда её сдвинули, и нажимает решение. Положение пишется прямо в CSS-переменные элемента: жест не перерисовывает карточку.
 */
export function useDecisionSwipe(options: DecisionSwipeOptions): (element: HTMLElement | null) => void {
  const [element, setElement] = useState<HTMLElement | null>(null)
  const latest = useRef(options)
  useLayoutEffect(() => { latest.current = options })

  useEffect(() => {
    if (!element) return
    let gesture: Gesture | null = null
    let timer: number | undefined
    let offset: Offset = { dx: 0, dy: 0 }

    const size = (): CardSize => ({ width: element.offsetWidth, height: element.offsetHeight })
    const paint = (state: DragState, dx: number, dy: number, direction: SwipeDirection | null, progress: number) => {
      element.setAttribute(DRAG_ATTR, state)
      if (direction) element.setAttribute(SWIPE_ATTR, direction)
      else element.removeAttribute(SWIPE_ATTR)
      element.style.setProperty('--drag-x', `${dx}px`)
      element.style.setProperty('--drag-y', `${dy}px`)
      element.style.setProperty('--drag-r', `${dx * TILT_DEG_PER_PX}deg`)
      element.style.setProperty('--drag-p', String(progress))
    }
    // Взятая карточка встаёт над страницей на своё же место: её не обрезают края и не перекрывает шапка.
    const lift = () => {
      const { left, top, width, height } = element.getBoundingClientRect()
      element.style.setProperty('--lift-left', `${left}px`)
      element.style.setProperty('--lift-top', `${top}px`)
      element.style.setProperty('--lift-w', `${width}px`)
      element.style.setProperty('--lift-h', `${height}px`)
    }
    const standStill = () => {
      element.removeAttribute(DRAG_ATTR)
      element.removeAttribute(SWIPE_ATTR)
      element.removeAttribute('style')
    }
    const back = () => {
      paint('back', 0, 0, null, 0)
      timer = window.setTimeout(standStill, ANIMATION_MS)
    }
    // Карточка улетает дальше по той же прямой, по которой её сдвинули.
    const fly = (direction: SwipeDirection) => {
      const { width, height } = size()
      const scale = direction === 'down' ? (height * FLY_DISTANCE) / offset.dy : (width * FLY_DISTANCE) / Math.abs(offset.dx)
      paint('fly', offset.dx * scale, offset.dy * scale, direction, 1)
      timer = window.setTimeout(() => {
        // Решение не увело с карточки (отказ, ошибка) — она возвращается.
        void latest.current.onSwipe(direction).finally(() => { if (element.isConnected) back() })
      }, ANIMATION_MS)
    }
    // После жеста отпускание пальца над кнопкой — не нажатие.
    const swallowClick = () => {
      const swallow = (e: Event) => { e.stopPropagation(); e.preventDefault() }
      element.addEventListener('click', swallow, { capture: true, once: true })
      window.setTimeout(() => element.removeEventListener('click', swallow, { capture: true }), 0)
    }

    const onDown = (e: PointerEvent) => {
      const busy = element.hasAttribute(DRAG_ATTR)
      if (!latest.current.enabled || busy || !e.isPrimary || e.button !== 0) return
      if (e.target instanceof Element && e.target.closest(TEXT_INPUT)) return
      gesture = { pointerId: e.pointerId, x: e.clientX, y: e.clientY, dragging: false, samples: [{ t: e.timeStamp, x: e.clientX, y: e.clientY }] }
    }
    const onMove = (e: PointerEvent) => {
      if (!gesture || e.pointerId !== gesture.pointerId) return
      offset = { dx: e.clientX - gesture.x, dy: e.clientY - gesture.y }
      if (!gesture.dragging) {
        const axis = swipeAxis(offset)
        if (!axis) return
        // Раскрытую карточку прокручивают: жест, начатый по вертикали, — её прокрутка.
        if (axis === 'y' && !latest.current.vertical) {
          gesture = null
          return
        }
        gesture.dragging = true
        lift()
        element.setPointerCapture(e.pointerId)
        window.getSelection()?.removeAllRanges()
      }
      e.preventDefault()
      gesture.samples = [...gesture.samples.filter(s => e.timeStamp - s.t <= SPEED_WINDOW_MS), { t: e.timeStamp, x: e.clientX, y: e.clientY }]
      const direction = dragDirection(offset, latest.current.vertical)
      paint('move', offset.dx, offset.dy, direction, dragProgress(direction, offset, size()))
    }
    const onUp = (e: PointerEvent) => {
      if (!gesture || e.pointerId !== gesture.pointerId) return
      const { dragging, samples } = gesture
      gesture = null
      if (!dragging) return
      swallowClick()
      const first = samples[0]
      const end = samples[samples.length - 1]
      const elapsed = first && end ? end.t - first.t : 0
      const velocity: Velocity = first && end && elapsed > 0
        ? { vx: (end.x - first.x) / elapsed, vy: (end.y - first.y) / elapsed }
        : { vx: 0, vy: 0 }
      const direction = releasedDirection(offset, velocity, size(), latest.current.vertical)
      if (direction && latest.current.canSwipe(direction)) fly(direction)
      else back()
    }
    const onCancel = (e: PointerEvent) => {
      if (!gesture || e.pointerId !== gesture.pointerId) return
      const { dragging } = gesture
      gesture = null
      if (dragging) back()
    }

    element.addEventListener('pointerdown', onDown)
    element.addEventListener('pointermove', onMove)
    element.addEventListener('pointerup', onUp)
    element.addEventListener('pointercancel', onCancel)
    return () => {
      window.clearTimeout(timer)
      element.removeEventListener('pointerdown', onDown)
      element.removeEventListener('pointermove', onMove)
      element.removeEventListener('pointerup', onUp)
      element.removeEventListener('pointercancel', onCancel)
      standStill()
    }
  }, [element])

  return setElement
}
