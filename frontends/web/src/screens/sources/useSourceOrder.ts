import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '@/api/client'
import type { SourceGrouping, SourceSort } from '@/api/types'
import { messageOf } from '@/lib/apiError'

export interface SourceOrder {
  grouping: SourceGrouping
  sort: SourceSort
}

interface Callbacks {
  /** Порядок сохранён: всё, что показывает источники по порядку, перечитывается. */
  onChanged: () => void
  onError: (message: string) => void
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
      .then(settings => { if (alive) setOrder({ grouping: settings.source_grouping, sort: settings.source_sort }) })
      .catch((e: unknown) => { if (alive) callbacks.current.onError(messageOf(e)) })
    return () => { alive = false }
  }, [])

  const save = useCallback(async (patch: { source_grouping: SourceGrouping } | { source_sort: SourceSort }) => {
    try {
      const settings = await api.updateSettings(patch)
      setOrder({ grouping: settings.source_grouping, sort: settings.source_sort })
      callbacks.current.onChanged()
    } catch (e) {
      callbacks.current.onError(messageOf(e))
    }
  }, [])

  return {
    order,
    setGrouping: (grouping: SourceGrouping) => save({ source_grouping: grouping }),
    setSort: (sort: SourceSort) => save({ source_sort: sort }),
  }
}
