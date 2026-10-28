import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { onNativeCheckForUpdates } from '@/lib/nativeHost'
import { SETTINGS_PATH } from '../TopNav'
import { useUpdates } from './useUpdates'

/** Раздел настроек, где кнопка Check for updates показывает итог проверки. */
const UPDATES_SETTINGS = `${SETTINGS_PATH}?section=updates`

/** Пункт Check for Updates… меню macOS-приложения: с любого экрана то же, что кнопка в настройках. */
export function useNativeCheckForUpdates(): void {
  const navigate = useNavigate()
  const { checkNow } = useUpdates()

  useEffect(() => onNativeCheckForUpdates(() => {
    navigate(UPDATES_SETTINGS)
    void checkNow()
  }), [navigate, checkNow])
}
