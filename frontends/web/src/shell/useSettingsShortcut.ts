import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { opensSettings } from '@/lib/hotkeys'
import { onNativeOpenSettings } from '@/lib/nativeHost'
import { SETTINGS_PATH } from './TopNav'

/** ⌘, с любого экрана открывает настройки; в macOS-приложении — и пункт меню Settings…. */
export function useSettingsShortcut(): void {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    const open = () => {
      if (pathname !== SETTINGS_PATH) navigate(SETTINGS_PATH)
    }
    const onKey = (e: KeyboardEvent) => {
      if (!opensSettings(e)) return
      e.preventDefault()
      open()
    }
    window.addEventListener('keydown', onKey)
    const unsubscribe = onNativeOpenSettings(open)
    return () => {
      window.removeEventListener('keydown', onKey)
      unsubscribe()
    }
  }, [navigate, pathname])
}
