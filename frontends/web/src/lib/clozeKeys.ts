import { OVERLAY } from './hotkeys'

export type ClozePanelKey = 'save' | 'cancel'

interface KeyLike {
  key: string
  metaKey: boolean
  ctrlKey: boolean
  altKey: boolean
  shiftKey: boolean
  repeat: boolean
  target: EventTarget | null
}

/**
 * Клавиши панели разметки cloze: Enter сохраняет, Esc отменяет.
 * Кнопка в фокусе нажимается Enter'ом сама: мышью кнопки разметки фокус не получают
 * (keepFocusOnMouseDown), значит на неё пришли с клавиатуры.
 */
export function clozePanelKey(e: KeyLike): ClozePanelKey | null {
  if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.repeat) return null
  if (document.querySelector(OVERLAY)) return null
  const target = e.target instanceof Element ? e.target : null
  // Поле правки фразы живёт своими клавишами.
  if (target?.closest('textarea')) return null
  if (e.key === 'Escape') return 'cancel'
  if (e.key !== 'Enter') return null
  if (target?.closest('button')) return null
  return 'save'
}
