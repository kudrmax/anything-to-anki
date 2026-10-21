/** Что-то указало на идущую смену уровня: запись получила 423 или настройки сохранены. */
const target = new EventTarget()
const EVENT = 'level-change'

/** Каждая запись, отклонённая на время смены уровня, отвечает этим кодом. */
export const LEVEL_CHANGE_STATUS = 423

export function notifyLevelChange(): void {
  target.dispatchEvent(new Event(EVENT))
}

export function onLevelChange(listener: () => void): () => void {
  target.addEventListener(EVENT, listener)
  return () => target.removeEventListener(EVENT, listener)
}
