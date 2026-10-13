import { useSyncExternalStore } from 'react'

// Порог телефона живёт только в styles/tokens.css: на телефоне он гасит десктопные элементы через этот токен.
const DESKTOP_DISPLAY_TOKEN = '--desktop-display'
const HIDDEN = 'none'

function subscribe(listener: () => void): () => void {
  window.addEventListener('resize', listener)
  return () => window.removeEventListener('resize', listener)
}

const isPhoneNow = (): boolean =>
  getComputedStyle(document.documentElement).getPropertyValue(DESKTOP_DISPLAY_TOKEN).trim() === HIDDEN

/** Телефонная раскладка: те же правила, по которым её включает CSS. */
export function usePhone(): boolean {
  return useSyncExternalStore(subscribe, isPhoneNow)
}
