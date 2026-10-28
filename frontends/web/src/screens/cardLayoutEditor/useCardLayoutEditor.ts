import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { CardLayoutEdit, CardLayoutView } from '@/api/types'
import type { LayoutSelection } from '@/cardLayout'

/** Раскладка в редакторе: каждая правка сразу уходит на сервер, он возвращает новую раскладку. */
export function useCardLayoutEditor() {
  const [view, setView] = useState<CardLayoutView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selection, setSelection] = useState<LayoutSelection | null>(null)

  useEffect(() => {
    api.getCardLayout().then(setView).catch(e => setError(e instanceof Error ? e.message : 'Failed to load the card layout'))
  }, [])

  const edit = useCallback(async (change: CardLayoutEdit) => {
    setError(null)
    try {
      setView(await api.editCardLayout(change))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to change the card layout')
    }
  }, [])

  /** Правка, после которой выбранное больше не там, где было, снимает выбор. */
  const editAndDeselect = useCallback(async (change: CardLayoutEdit) => {
    setSelection(null)
    await edit(change)
  }, [edit])

  return { view, error, selection, select: setSelection, edit, editAndDeselect }
}

export type CardLayoutEditor = ReturnType<typeof useCardLayoutEditor>
