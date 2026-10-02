import { useState } from 'react'
import type { StoredCandidate } from '@/api/types'

export interface ShownCandidates {
  shown: StoredCandidate[]
  hiddenCount: number
  nextPageCount: number
  pages: number
}

/**
 * Первые `pages` страниц по `pageSize` кандидатов, но не меньше, чем нужно,
 * чтобы текущий кандидат был виден. `pageSize` null — показываем всех.
 */
export function shownCandidates(
  candidates: StoredCandidate[],
  pageSize: number | null,
  currentId: number | null,
  pages: number,
): ShownCandidates {
  if (pageSize == null) {
    return { shown: candidates, hiddenCount: 0, nextPageCount: 0, pages }
  }
  const currentIndex = candidates.findIndex(c => c.id === currentId)
  const neededPages = currentIndex < 0 ? 1 : Math.ceil((currentIndex + 1) / pageSize)
  const shownPages = Math.max(pages, neededPages)
  const shown = candidates.slice(0, shownPages * pageSize)
  const hiddenCount = candidates.length - shown.length
  return { shown, hiddenCount, nextPageCount: Math.min(pageSize, hiddenCount), pages: shownPages }
}

/**
 * Показывает кандидатов страницами, остальные — по «Show more».
 * Граница не откатывается назад, когда текущий кандидат возвращается выше.
 * Смена `resetKey` (источник, сортировка) возвращает одну страницу.
 */
export function useShownCandidates(
  candidates: StoredCandidate[],
  pageSize: number | null,
  currentId: number | null,
  resetKey: string,
) {
  const [state, setState] = useState({ resetKey, pages: 1 })
  const pages = state.resetKey === resetKey ? state.pages : 1
  const shown = shownCandidates(candidates, pageSize, currentId, pages)
  if (state.resetKey !== resetKey || shown.pages !== state.pages) {
    setState({ resetKey, pages: shown.pages })
  }
  return { ...shown, showMore: () => setState({ resetKey, pages: shown.pages + 1 }) }
}
