export type ReviewAction = 'prev' | 'next' | 'learn' | 'cloze' | 'known' | 'skip' | 'audio'

const KEYS: Record<string, ReviewAction> = {
  ArrowUp: 'prev', ArrowDown: 'next', '1': 'learn', '2': 'cloze', '3': 'known', '4': 'skip', ' ': 'audio',
}
const OVERLAY = '[role="dialog"], [role="menu"]'
const BLOCKING = `input, textarea, select, [contenteditable="true"], ${OVERLAY}`
const ACTIVATED_BY_SPACE = 'button, a'
/** Удержание клавиши листает фразы, но не оценивает их подряд. */
const REPEATABLE: ReviewAction[] = ['prev', 'next']

interface KeyLike {
  key: string
  metaKey: boolean
  ctrlKey: boolean
  altKey: boolean
  repeat: boolean
  target: EventTarget | null
}

export function reviewAction(e: KeyLike): ReviewAction | null {
  if (e.metaKey || e.ctrlKey || e.altKey) return null
  // Открытое меню или окно перехватывает клавиатуру, где бы ни был фокус.
  if (document.querySelector(OVERLAY)) return null
  if (e.target instanceof Element) {
    if (e.target.closest(BLOCKING)) return null
    // Пробел на кнопке в фокусе — это нажатие самой кнопки.
    if (e.key === ' ' && e.target.closest(ACTIVATED_BY_SPACE)) return null
  }
  const action = KEYS[e.key] ?? null
  if (action && e.repeat && !REPEATABLE.includes(action)) return null
  return action
}
