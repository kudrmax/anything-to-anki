import { useEffect, type RefObject } from 'react'
import { BLOCK_ATTR, ROW_ATTR } from '@/cardLayout'
import { reviewAction } from '@/lib/hotkeys'
import { VIEW_CONTROL_ATTR } from '@/screens/review/viewControl'

/** Что можно нажать на экране образца: кнопки вида, блоки и линии карточки. */
const ALLOWED = `[${VIEW_CONTROL_ATTR}], [${BLOCK_ATTR}], [${ROW_ATTR}]`
/** Всё, что что-то делает: такие нажатия на образце гасятся. */
const ACTIONS = 'button, a, input, select, textarea, [role="button"], [role="menuitem"], [role="option"], label'

/**
 * Образец — экран ревью целиком, но решать и менять на нём нечего: работают только кнопки вида
 * (стрелки, панели, список) и сама раскладка. Остальные нажатия и клавиши ревью гасятся до экрана.
 */
export function useBlockedActions(screenRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const screen = screenRef.current
    if (!screen) return
    const onClick = (e: MouseEvent) => {
      const target = e.target instanceof Element ? e.target : null
      if (!target || target.closest(ALLOWED)) return
      if (target.closest(ACTIONS)) {
        e.preventDefault()
        e.stopPropagation()
      }
    }
    const onKey = (e: KeyboardEvent) => {
      const action = reviewAction(e)
      if (action && action !== 'prev' && action !== 'next') e.stopImmediatePropagation()
    }
    const onPaste = (e: ClipboardEvent) => e.stopImmediatePropagation()
    screen.addEventListener('click', onClick, true)
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('paste', onPaste, true)
    return () => {
      screen.removeEventListener('click', onClick, true)
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('paste', onPaste, true)
    }
  }, [screenRef])
}
