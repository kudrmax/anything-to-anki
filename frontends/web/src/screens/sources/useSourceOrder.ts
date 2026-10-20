import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { Settings, SourceGrouping, SourceSort, SourceSortDirection } from '@/api/types'
import { messageOf } from '@/lib/apiError'

export interface SourceOrder {
  grouping: SourceGrouping
  sort: SourceSort
  direction: SourceSortDirection
}

interface Callbacks {
  /** Порядок сохранён: всё, что показывает источники по порядку, перечитывается. */
  onChanged: () => void
  onError: (message: string) => void
}

function orderOf(settings: Settings): SourceOrder {
  return { grouping: settings.source_grouping, sort: settings.source_sort, direction: settings.source_sort_direction }
}

/** Выбор порядка источников живёт в настройках backend'а: один на все области. */
export function useSourceOrder(props: Callbacks) {
  const [order, setOrder] = useState<SourceOrder | null>(null)
  const callbacks = useRef(props)
  useLayoutEffect(() => {
    callbacks.current = props
  })

  useEffect(() => {
    let alive = true
    api.getSettings()
      .then(settings => { if (alive) setOrder(orderOf(settings)) })
      .catch((e: unknown) => { if (alive) callbacks.current.onError(messageOf(e)) })
    return () => { alive = false }
  }, [])

  const save = useCallback(async (patch: Partial<Pick<Settings, 'source_grouping' | 'source_sort' | 'source_sort_direction'>>) => {
    try {
      const settings = await api.updateSettings(patch)
      setOrder(orderOf(settings))
      callbacks.current.onChanged()
    } catch (e) {
      callbacks.current.onError(messageOf(e))
    }
  }, [])

  return {
    order,
    setGrouping: (grouping: SourceGrouping) => save({ source_grouping: grouping }),
    setSort: (sort: SourceSort) => save({ source_sort: sort }),
    setDirection: (direction: SourceSortDirection) => save({ source_sort_direction: direction }),
  }
}
