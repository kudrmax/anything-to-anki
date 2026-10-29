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

/** Сдвиг карточки от места, где её взяли. */
export interface Offset {
  dx: number
  dy: number
}

/** Скорость пальца в момент отпускания, px/ms. */
export interface Velocity {
  vx: number
  vy: number
}

export interface CardSize {
  width: number
  height: number
}

/** Куда пошёл палец в начале жеста; null — ещё не ушёл дальше тапа. */
export function swipeAxis({ dx, dy }: Offset): SwipeAxis | null {
  if (Math.hypot(dx, dy) < SLOP_PX) return null
  return Math.abs(dx) >= Math.abs(dy) ? 'x' : 'y'
}

/**
 * Решение, к которому сейчас сдвинута карточка: её тянут куда угодно, решает то, куда она ушла дальше всего.
 * Вверх решения нет; вниз — только если вертикаль у свайпа, а не у прокрутки.
 */
export function dragDirection({ dx, dy }: Offset, vertical: boolean): SwipeDirection | null {
  if (Math.abs(dx) >= Math.abs(dy)) return dx > 0 ? 'right' : dx < 0 ? 'left' : null
  return vertical && dy > 0 ? 'down' : null
}

/** Насколько карточку дотянули до порога этого решения: 0…1. */
export function dragProgress(direction: SwipeDirection | null, { dx, dy }: Offset, size: CardSize): number {
  if (!direction) return 0
  const reach = direction === 'down' ? dy / (size.height * VERTICAL_SHARE) : Math.abs(dx) / (size.width * HORIZONTAL_SHARE)
  return Math.min(reach, 1)
}

/** Решение отпущенной карточки: дотянули до порога или бросили; иначе она возвращается на место. */
export function releasedDirection(offset: Offset, { vx, vy }: Velocity, size: CardSize, vertical: boolean): SwipeDirection | null {
  const direction = dragDirection(offset, vertical)
  if (!direction) return null
  const distance = direction === 'down' ? offset.dy : Math.abs(offset.dx)
  const speed = direction === 'down' ? vy : direction === 'right' ? vx : -vx
  const flung = speed >= FLING_SPEED && distance >= FLING_MIN_PX
  return dragProgress(direction, offset, size) >= 1 || flung ? direction : null
}
