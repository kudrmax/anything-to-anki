import { useEffect, useState } from 'react'
import { onNativeCheckForUpdates } from '@/lib/nativeHost'
import { useUpdates, type CheckOutcome } from './useUpdates'

/**
 * Пункт Check for Updates… меню macOS-приложения: проверка поверх текущего экрана. Новая
 * версия открывает попап обновления; иначе возвращается итог, который показать.
 */
export function useNativeCheckForUpdates(): { outcome: CheckOutcome | null; dismiss: () => void } {
  const { checkNow } = useUpdates()
  const [outcome, setOutcome] = useState<CheckOutcome | null>(null)

  useEffect(() => onNativeCheckForUpdates(() => {
    void checkNow().then(setOutcome)
  }), [checkNow])

  return { outcome, dismiss: () => setOutcome(null) }
}
