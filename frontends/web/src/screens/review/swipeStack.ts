import type { StoredCandidate } from '@/api/types'
import { landingAfter } from './pressAhead'
import type { ReviewState } from './reviewState'
import { SWIPE_DECISION, type SwipeDirection } from './swipeDecision'
import { upcomingCards } from './upcomingCards'

export const SWIPE_DIRECTIONS: SwipeDirection[] = ['right', 'left', 'down']

/**
 * Стопка на телефоне: какая карточка лежит под текущей для каждого свайпа — та, куда экран перейдёт после него.
 * Skip закрывает одну карточку, Learn и Know — всю лемму, поэтому под ними бывают разные карточки.
 * Свайп уже принятого решения ведёт к следующей карточке списка.
 */
export function cardsUnder(state: ReviewState, current: StoredCandidate): Map<number, SwipeDirection[]> {
  const under = new Map<number, SwipeDirection[]>()
  for (const direction of SWIPE_DIRECTIONS) {
    const button = current.state.buttons.find(b => b.button === SWIPE_DECISION[direction])
    if (!button || button.command === null) continue
    const next = button.pressed
      ? upcomingCards(state, 1)[0]?.phrase_id ?? null
      : landingAfter(state, current.phrase_id, button.closes)
    if (next !== null) under.set(next, [...(under.get(next) ?? []), direction])
  }
  return under
}
