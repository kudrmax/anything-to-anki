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

/** Строка запроса области: у All параметра нет. */
export const scopeQuery = (scope: Scope): string => (scope === 'all' ? '' : `?${PARAM}=${scope}`)

interface ScopeChange { replace?: boolean }

/** Открытая область живёт в URL: ссылка на коллекцию открывается напрямую, назад из Review — туда же. */
export function useScope(): [Scope, (next: Scope, change?: ScopeChange) => void] {
  const [params, setParams] = useSearchParams()
  const scope = parseScope(params.get(PARAM))
  const setScope = useCallback((next: Scope, change: ScopeChange = {}) => {
    setParams(previous => {
      const updated = new URLSearchParams(previous)
      if (next === 'all') updated.delete(PARAM)
      else updated.set(PARAM, String(next))
      return updated
    }, { replace: change.replace })
  }, [setParams])
  return [scope, setScope]
}
