import { useContext, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { CardLayoutView } from '@/api/types'
import { CardLayoutViewContext } from './editing'

/** Раскладка карточки: сохранённая или та, что сейчас правят в редакторе; null — пока не загрузилась. */
export function useCardLayout(): CardLayoutView | null {
  const edited = useContext(CardLayoutViewContext)
  const [saved, setSaved] = useState<CardLayoutView | null>(null)
  const fromEditor = edited !== undefined
  useEffect(() => {
    if (!fromEditor) api.getCardLayout().then(setSaved).catch(() => {})
  }, [fromEditor])
  return fromEditor ? edited : saved
}
