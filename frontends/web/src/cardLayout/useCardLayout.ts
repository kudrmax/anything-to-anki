import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { CardLayoutView } from '@/api/types'

/** Сохранённая раскладка карточки; null — пока не загрузилась. */
export function useCardLayout(): CardLayoutView | null {
  const [view, setView] = useState<CardLayoutView | null>(null)
  useEffect(() => {
    api.getCardLayout().then(setView).catch(() => {})
  }, [])
  return view
}
