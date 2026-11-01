import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Scope, SetScope, SourcesView } from '@/api/types'

const PARAM = 'scope'
const CANDIDATE_PARAM = 'candidate'
const REVIEW_PATH = '/review'
const EXPORT_PATH = '/export'
const ID = /^\d+$/
const SOURCE = /^source-(\d+)$/
const SOURCES_PATH = '/'

export function parseScope(raw: string | null): Scope {
  if (raw === 'unsorted') return 'unsorted'
  if (raw !== null && ID.test(raw)) return Number(raw)
  return 'all'
}

/** Раздел экрана источников из ссылки: без параметра — Recent. */
export const parseView = (raw: string | null): SourcesView => (raw === null ? 'recent' : parseScope(raw))

/** Адрес раздела экрана источников: у Recent параметра нет, у All он есть. */
export const viewPath = (view: SourcesView): string => (view === 'recent' ? SOURCES_PATH : `${SOURCES_PATH}?${PARAM}=${view}`)

export const sourceScope = (id: number): SetScope => `source-${id}`

/** Набор из одного источника, а не коллекция или раздел. */
export const isSourceScope = (scope: SetScope): boolean => typeof scope === 'string' && SOURCE.test(scope)

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

/** Открытый раздел живёт в URL: ссылка на коллекцию открывается напрямую, назад из Review — туда же. */
export function useView(): [SourcesView, (next: SourcesView, change?: ScopeChange) => void] {
  const [params, setParams] = useSearchParams()
  const view = parseView(params.get(PARAM))
  const setView = useCallback((next: SourcesView, change: ScopeChange = {}) => {
    setParams(previous => {
      const updated = new URLSearchParams(previous)
      if (next === 'recent') updated.delete(PARAM)
      else updated.set(PARAM, String(next))
      return updated
    }, { replace: change.replace })
  }, [setParams])
  return [view, setView]
}

/** Адрес экспорта набора. */
export const exportPath = (scope: SetScope): string => `${EXPORT_PATH}${scopeQuery(scope)}`
