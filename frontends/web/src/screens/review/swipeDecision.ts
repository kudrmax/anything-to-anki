import type { DecisionButton } from '@/api/types'

export type SwipeDirection = 'right' | 'left' | 'down'
export type SwipeAxis = 'x' | 'y'

/** Какую кнопку решения нажимает свайп карточки. */
export const SWIPE_DECISION: Record<SwipeDirection, DecisionButton> = { right: 'learn', left: 'known', down: 'skip' }

/** Сдвиг, после которого касание — уже жест, а не тап. */
const SLOP_PX = 10
/** Доля ширины карточки, за которой отпущенная карточка улетает вбок. */
const HORIZONTAL_SHARE = 0.3
/** Доля высоты карточки, за которой отпущенная карточка улетает вниз. */
const VERTICAL_SHARE = 0.2
/** Бросок: скорость, с которой карточка улетает и недотянутой, px/ms. */
const FLING_SPEED = 0.5
/** Короче этого броском не считается: случайный рывок пальца. */
const FLING_MIN_PX = 40

export interface Drag {
  dx: number
  dy: number
  /** Скорость вдоль оси жеста в момент отпускания, px/ms. */
  speed: number
}

export interface CardSize {
  width: number
  height: number
}

/** Ось жеста; null — палец ещё не ушёл дальше тапа. */
export function swipeAxis(dx: number, dy: number): SwipeAxis | null {
  if (Math.hypot(dx, dy) < SLOP_PX) return null
  return Math.abs(dx) >= Math.abs(dy) ? 'x' : 'y'
}

/** Куда тянут карточку по оси жеста; вверх решения нет. */
export function dragDirection(axis: SwipeAxis, { dx, dy }: Pick<Drag, 'dx' | 'dy'>): SwipeDirection | null {
  if (axis === 'x') return dx > 0 ? 'right' : dx < 0 ? 'left' : null
  return dy > 0 ? 'down' : null
}

/** Насколько карточку дотянули до порога решения: 0…1. */
export function dragProgress(axis: SwipeAxis, { dx, dy }: Pick<Drag, 'dx' | 'dy'>, size: CardSize): number {
  const reach = axis === 'x' ? Math.abs(dx) / (size.width * HORIZONTAL_SHARE) : Math.max(dy, 0) / (size.height * VERTICAL_SHARE)
  return Math.min(reach, 1)
}

/** Решение отпущенной карточки: дотянули до порога или бросили; иначе она возвращается на место. */
export function releasedDirection(axis: SwipeAxis, drag: Drag, size: CardSize): SwipeDirection | null {
  const direction = dragDirection(axis, drag)
  if (!direction) return null
  const distance = axis === 'x' ? Math.abs(drag.dx) : drag.dy
  const flung = drag.speed >= FLING_SPEED && distance >= FLING_MIN_PX
  return dragProgress(axis, drag, size) >= 1 || flung ? direction : null
}
