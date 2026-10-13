import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Scope } from '@/api/types'

const PARAM = 'scope'
const ID = /^\d+$/

export function parseScope(raw: string | null): Scope {
  if (raw === 'unsorted') return 'unsorted'
  if (raw !== null && ID.test(raw)) return Number(raw)
  return 'all'
}

/** Открытая область живёт в URL: ссылка на коллекцию открывается напрямую, назад из Review — туда же. */
export function useScope(): [Scope, (next: Scope) => void] {
  const [params, setParams] = useSearchParams()
  const scope = parseScope(params.get(PARAM))
  const setScope = useCallback((next: Scope) => {
    setParams(next === 'all' ? {} : { [PARAM]: String(next) })
  }, [setParams])
  return [scope, setScope]
}
