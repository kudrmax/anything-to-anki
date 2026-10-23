import { useCallback, useEffect, useRef } from 'react'
import { api } from '@/api/client'
import type { ImageOption } from '@/api/types'
import type { ReviewState } from './reviewState'
import { upcomingCards } from './upcomingCards'

export const SUGGESTED_PICTURES = 5
const PREFETCHED_CARDS = 5
/** Как часто спрашивать сервер, пока поиск ещё идёт: сам поиск идёт на сервере в фоне. */
export const SUGGESTION_POLL_MS = 2000
/** Сколько ждать подсказок: дольше — их нет, слово спросят снова при следующем показе. */
const SUGGESTION_WAIT_MS = 60_000

/** Подсказки картинок слова; найденные один раз — до конца ревью. */
export type PictureSuggestionsLoader = (wordId: number) => Promise<ImageOption[]>

const preload = (options: ImageOption[]) => {
  for (const option of options) new Image().src = option.url
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Картинки слова, когда сервер их нашёл; каждый запрос короткий — соединения остаются ревью.
 * Спрашивает, пока слово нужно (`wanted`): пролистанное больше не спрашивают, его спросят при следующем показе.
 */
async function suggested(wordId: number, wanted: () => boolean): Promise<ImageOption[]> {
  const giveUpAt = Date.now() + SUGGESTION_WAIT_MS
  for (;;) {
    const answer = await api.suggestTargetImages(wordId)
    if (answer.status === 'ready') return answer.options.slice(0, SUGGESTED_PICTURES)
    if (answer.status === 'failed' || Date.now() >= giveUpAt) throw new Error('No picture suggestions')
    await sleep(SUGGESTION_POLL_MS)
    if (!wanted()) throw new Error('No longer wanted')
  }
}

/**
 * Подсказки картинок для слова текущей карточки и заранее — для следующих карточек списка.
 * Ищет их сервер в фоне: нашёл — показываем, нет — пока не показываем. Неудачный поиск не запоминается.
 */
export function usePictureSuggestions(state: ReviewState, enabled: boolean): PictureSuggestionsLoader | null {
  const found = useRef(new Map<number, Promise<ImageOption[]>>())
  /** Слова текущей карточки и тех, что идут следом: только их и спрашивают. */
  const wanted = useRef(new Set<number>())

  const load = useCallback<PictureSuggestionsLoader>(wordId => {
    const known = found.current.get(wordId)
    if (known) return known
    const search = suggested(wordId, () => wanted.current.has(wordId)).catch(() => {
      found.current.delete(wordId)
      return []
    })
    found.current.set(wordId, search)
    return search
  }, [])

  useEffect(() => {
    const upcoming = upcomingCards(state, PREFETCHED_CARDS)
    const current = state.currentId === null ? undefined : state.cards.get(state.currentId)
    wanted.current = new Set([...(current ? [current] : []), ...upcoming].map(card => card.word_id))
    if (!enabled) return
    for (const card of upcoming) {
      if (!card.meaning_image_path && !found.current.has(card.word_id)) void load(card.word_id).then(preload)
    }
  }, [enabled, state, load])

  return enabled ? load : null
}
