import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Scope, SetScope } from '@/api/types'

const PARAM = 'scope'
const CANDIDATE_PARAM = 'candidate'
const REVIEW_PATH = '/review'
const EXPORT_PATH = '/export'
const ID = /^\d+$/
const SOURCE = /^source-(\d+)$/

export function parseScope(raw: string | null): Scope {
  if (raw === 'unsorted') return 'unsorted'
  if (raw !== null && ID.test(raw)) return Number(raw)
  return 'all'
}

export const sourceScope = (id: number): SetScope => `source-${id}`

/** Набор из ссылки: один источник (`source-7`) не путается с коллекцией (`7`). */
export function parseSetScope(raw: string | null): SetScope {
  const source = raw === null ? null : SOURCE.exec(raw)
  return source ? sourceScope(Number(source[1])) : parseScope(raw)
}

/** Строка запроса области: у All параметра нет. */
export const scopeQuery = (scope: SetScope): string => (scope === 'all' ? '' : `?${PARAM}=${scope}`)

/** Один адрес ревью для любого набора; с карточкой ревью открывается на ней. */
export function reviewPath(scope: SetScope, candidateId?: number): string {
  const params = new URLSearchParams()
  if (scope !== 'all') params.set(PARAM, String(scope))
  if (candidateId !== undefined) params.set(CANDIDATE_PARAM, String(candidateId))
  const query = params.toString()
  return query ? `${REVIEW_PATH}?${query}` : REVIEW_PATH
}

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

/** Адрес экспорта набора. */
export const exportPath = (scope: SetScope): string => `${EXPORT_PATH}${scopeQuery(scope)}`
