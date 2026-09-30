import { useEffect, useSyncExternalStore } from 'react'
import { themeModePref, type ThemePref } from './preferences'

const SYSTEM_DARK = '(prefers-color-scheme: dark)'

export function resolveTheme(pref: ThemePref, systemDark: boolean): 'light' | 'dark' {
  if (pref === 'system') return systemDark ? 'dark' : 'light'
  return pref
}

const listeners = new Set<() => void>()
let current: ThemePref = themeModePref.read()

/** Одно хранилище на всё приложение: настройку видят и Settings, и каркас. */
export const themeStore = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener)
    return () => { listeners.delete(listener) }
  },
  getSnapshot: (): ThemePref => current,
  set(pref: ThemePref): void {
    current = pref
    themeModePref.write(pref)
    listeners.forEach(listener => listener())
  },
}

export function useTheme(): { pref: ThemePref; setPref: (pref: ThemePref) => void } {
  const pref = useSyncExternalStore(themeStore.subscribe, themeStore.getSnapshot)
  return { pref, setPref: themeStore.set }
}

/** Применяет тему к документу и следит за системной. Вызывается один раз — в каркасе. */
export function useApplyTheme(): void {
  const { pref } = useTheme()
  useEffect(() => {
    const media = window.matchMedia(SYSTEM_DARK)
    const apply = () => { document.documentElement.dataset.theme = resolveTheme(pref, media.matches) }
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [pref])
}
