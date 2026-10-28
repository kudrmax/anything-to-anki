import { useEffect, useState } from 'react'
import { onNativeCheckForUpdates } from '@/lib/nativeHost'
import { useUpdates, type CheckOutcome } from './useUpdates'

/** Окно проверки из меню: идёт проверка или её итог; закрыто — null. */
export type NativeCheck = 'checking' | CheckOutcome

/**
 * Пункт Check for Updates… меню macOS-приложения: проверка поверх текущего экрана. Окно
 * открывается сразу и показывает, что проверка идёт; новая версия закрывает его и открывает
 * попап обновления, иначе в нём остаётся итог.
 */
export function useNativeCheckForUpdates(): { check: NativeCheck | null; dismiss: () => void } {
  const { checkNow } = useUpdates()
  const [check, setCheck] = useState<NativeCheck | null>(null)

  useEffect(() => onNativeCheckForUpdates(() => {
    setCheck('checking')
    void checkNow().then(setCheck)
  }), [checkNow])

  return { check, dismiss: () => setCheck(null) }
}
