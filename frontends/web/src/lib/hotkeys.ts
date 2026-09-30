export type ReviewAction = 'prev' | 'next' | 'learn' | 'known' | 'skip' | 'audio'

const KEYS: Record<string, ReviewAction> = {
  ArrowUp: 'prev', ArrowDown: 'next', '1': 'learn', '2': 'known', '3': 'skip', ' ': 'audio',
}
const BLOCKING = 'input, textarea, select, [contenteditable="true"], [role="dialog"], [role="menu"]'
const ACTIVATED_BY_SPACE = 'button, a'

interface KeyLike {
  key: string
  metaKey: boolean
  ctrlKey: boolean
  altKey: boolean
  target: EventTarget | null
}

export function reviewAction(e: KeyLike): ReviewAction | null {
  if (e.metaKey || e.ctrlKey || e.altKey) return null
  if (e.target instanceof Element) {
    if (e.target.closest(BLOCKING)) return null
    // Пробел на кнопке в фокусе — это нажатие самой кнопки.
    if (e.key === ' ' && e.target.closest(ACTIVATED_BY_SPACE)) return null
  }
  return KEYS[e.key] ?? null
}
