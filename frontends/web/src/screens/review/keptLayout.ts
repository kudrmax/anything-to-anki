import type { StoredCandidate } from '@/api/types'

/**
 * Свежие данные карточек в порядке и разделах, снятых при загрузке списка: нажатая карточка
 * остаётся на месте, пока список не перезагрузят. Карточка, которой больше нет, уходит; новая
 * встаёт за той, за которой стоит в свежем списке.
 */
export function keepLayout(previous: StoredCandidate[], fresh: StoredCandidate[]): StoredCandidate[] {
  const placed = new Map(previous.map(c => [c.phrase_id, c]))
  const freshById = new Map(fresh.map(c => [c.phrase_id, c]))
  const following = new Map<number | null, StoredCandidate[]>()
  let anchor: number | null = null
  for (const card of fresh) {
    if (placed.has(card.phrase_id)) {
      anchor = card.phrase_id
      continue
    }
    const after = following.get(anchor)
    if (after) after.push(card)
    else following.set(anchor, [card])
  }
  const kept: StoredCandidate[] = [...(following.get(null) ?? [])]
  for (const old of previous) {
    const card = freshById.get(old.phrase_id)
    if (!card) continue
    kept.push({ ...card, section: old.section })
    kept.push(...(following.get(old.phrase_id) ?? []))
  }
  return kept
}
