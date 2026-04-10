import { createContext, useContext, useEffect, useState } from 'react'
import { themePref, type ThemeName } from './preferences'

interface ThemeCtx { theme: ThemeName; setTheme: (t: ThemeName) => void }
const ThemeContext = createContext<ThemeCtx>({ theme: 'cosmic', setTheme: () => {} })

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(() => themePref.read())

  const setTheme = (t: ThemeName) => {
    setThemeState(t)
    themePref.write(t)
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
