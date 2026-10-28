import { useEffect, useState } from 'react'
import type { ImageOption, StoredCandidate } from '@/api/types'
import { PictureSuggestionsView } from '@/cardLayout'
import type { Review } from './useReview'
import { SUGGESTED_PICTURES, type PictureSuggestionsLoader } from './usePictureSuggestions'

interface PictureSuggestionsProps {
  candidate: StoredCandidate
  review: Review
  load: PictureSuggestionsLoader
}

/** Первые картинки поиска прямо на карточке: клик ставит картинку, без клика ничего не сохраняется. */
export function PictureSuggestions({ candidate, review, load }: PictureSuggestionsProps) {
  const [found, setFound] = useState<{ wordId: number; options: ImageOption[] } | null>(null)
  const wordId = candidate.word_id

  useEffect(() => {
    let alive = true
    void load(wordId).then(options => { if (alive) setFound({ wordId, options }) })
    return () => { alive = false }
  }, [wordId, load])

  const options = found?.wordId === wordId ? found.options : null

  if (options?.length === 0) return null
  return (
    <PictureSuggestionsView
      options={options}
      placeholders={SUGGESTED_PICTURES}
      applying={review.busy.image.has(candidate.phrase_id)}
      onPick={url => void review.applyImage(candidate.phrase_id, url)}
    />
  )
}
