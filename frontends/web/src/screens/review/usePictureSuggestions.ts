import { useCallback, useEffect, useRef } from 'react'
import { api } from '@/api/client'
import type { ImageOption } from '@/api/types'
import type { ReviewState } from './reviewState'
import { upcomingCards } from './upcomingCards'

export const SUGGESTED_PICTURES = 5
const PREFETCHED_CARDS = 5

/** Подсказки картинок слова; найденные один раз — до конца ревью. */
export type PictureSuggestionsLoader = (wordId: number) => Promise<ImageOption[]>

const preload = (options: ImageOption[]) => {
  for (const option of options) new Image().src = option.url
}

/**
 * Ищет картинки для слова текущей карточки и заранее — для следующих карточек списка,
 * чтобы на них подсказки появлялись сразу. Неудачный поиск не запоминается: его повторят.
 */
export function usePictureSuggestions(state: ReviewState, enabled: boolean): PictureSuggestionsLoader | null {
  const found = useRef(new Map<number, Promise<ImageOption[]>>())

  const load = useCallback<PictureSuggestionsLoader>(wordId => {
    const known = found.current.get(wordId)
    if (known) return known
    const search = api.searchTargetImages(wordId).then(
      result => result.options.slice(0, SUGGESTED_PICTURES),
      () => {
        found.current.delete(wordId)
        return []
      },
    )
    found.current.set(wordId, search)
    return search
  }, [])

  useEffect(() => {
    if (!enabled) return
    for (const card of upcomingCards(state, PREFETCHED_CARDS)) {
      if (!card.meaning_image_path && !found.current.has(card.word_id)) void load(card.word_id).then(preload)
    }
  }, [enabled, state, load])

  return enabled ? load : null
}
