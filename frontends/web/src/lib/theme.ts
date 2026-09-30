import { useEffect, useState } from 'react'
import { themeModePref, type ThemePref } from './preferences'

const SYSTEM_DARK = '(prefers-color-scheme: dark)'

export function resolveTheme(pref: ThemePref, systemDark: boolean): 'light' | 'dark' {
  if (pref === 'system') return systemDark ? 'dark' : 'light'
  return pref
}

export function useTheme(): { pref: ThemePref; setPref: (p: ThemePref) => void } {
  const [pref, setPrefState] = useState<ThemePref>(() => themeModePref.read())

  useEffect(() => {
    const media = window.matchMedia(SYSTEM_DARK)
    const apply = () => { document.documentElement.dataset.theme = resolveTheme(pref, media.matches) }
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [pref])

  const setPref = (p: ThemePref) => { themeModePref.write(p); setPrefState(p) }
  return { pref, setPref }
}
