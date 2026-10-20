export type ReviewAction =
  | 'prev' | 'next'
  | 'learn' | 'cloze' | 'known' | 'skip'
  | 'audio'
  | 'image' | 'edit' | 'regenerate' | 'report'

export type ToolAction = Extract<ReviewAction, 'image' | 'edit' | 'regenerate' | 'report'>

/** Клавиши — по физическому положению (KeyboardEvent.code), чтобы работали в любой раскладке. */
const KEYS: Record<string, ReviewAction> = {
  ArrowUp: 'prev', ArrowLeft: 'prev', ArrowDown: 'next', ArrowRight: 'next',
  KeyL: 'learn', Space: 'learn', KeyC: 'cloze', KeyK: 'known', KeyS: 'skip',
  KeyA: 'audio',
  KeyI: 'image', KeyE: 'edit', KeyR: 'regenerate', KeyF: 'report',
}
/** Как клавиша действия подписана на кнопке. */
export const KEY_LABEL: Record<Exclude<ReviewAction, 'prev' | 'next'>, string> = {
  learn: 'L', cloze: 'C', known: 'K', skip: 'S',
  audio: 'A',
  image: 'I', edit: 'E', regenerate: 'R', report: 'F',
}
const TOOLS: ReviewAction[] = ['image', 'edit', 'regenerate', 'report']
export const OVERLAY = '[role="dialog"], [role="menu"]'
const TYPING = 'input, textarea, select, [contenteditable="true"]'
const BLOCKING = `${TYPING}, ${OVERLAY}`
const ACTIVATED_BY_SPACE = 'button, a'
/** В разметке cloze карточка не меняется: оценка сначала закрывает разметку. */
const ALLOWED_IN_CLOZE_MARKUP: ReviewAction[] = ['learn', 'known', 'skip', 'audio']
/** Удержание клавиши листает фразы, но не оценивает их подряд. */
const REPEATABLE: ReviewAction[] = ['prev', 'next']

interface KeyLike {
  code: string
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
    if (e.code === 'Space' && e.target.closest(ACTIVATED_BY_SPACE)) return null
  }
  const action = KEYS[e.code] ?? null
  if (action && e.repeat && !REPEATABLE.includes(action)) return null
  return action
}

/** Клавиша инструмента и при открытом меню или окне: повторное нажатие закрывает открытое ею. */
export function toolKey(e: KeyLike): ToolAction | null {
  if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return null
  if (e.target instanceof Element && e.target.closest(TYPING)) return null
  const action = KEYS[e.code] ?? null
  return action && isToolAction(action) ? action : null
}

export function isToolAction(action: ReviewAction): action is ToolAction {
  return TOOLS.includes(action)
}

export function allowedInClozeMarkup(action: ReviewAction): boolean {
  return ALLOWED_IN_CLOZE_MARKUP.includes(action)
}
