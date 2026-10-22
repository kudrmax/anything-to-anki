import { useEffect, useState, type SyntheticEvent } from 'react'
import { Plus } from 'lucide-react'
import type { ImageOption, StoredCandidate } from '@/api/types'
import { Icon } from '@/ui'
import type { Review } from './useReview'
import { SUGGESTED_PICTURES, type PictureSuggestionsLoader } from './usePictureSuggestions'
import css from './review.module.css'

interface PictureSuggestionsProps {
  candidate: StoredCandidate
  review: Review
  load: PictureSuggestionsLoader
}

const PLACEHOLDERS: null[] = Array.from({ length: SUGGESTED_PICTURES }, () => null)

const hideBrokenTile = (e: SyntheticEvent<HTMLImageElement>) => {
  const tile = e.currentTarget.parentElement
  if (tile) tile.hidden = true
}

/** Первые картинки поиска прямо на карточке: клик ставит картинку, без клика ничего не сохраняется. */
export function PictureSuggestions({ candidate, review, load }: PictureSuggestionsProps) {
  const [found, setFound] = useState<{ wordId: number; options: ImageOption[] } | null>(null)
  const applying = review.busy.image.has(candidate.phrase_id)
  const wordId = candidate.word_id

  useEffect(() => {
    let alive = true
    void load(wordId).then(options => { if (alive) setFound({ wordId, options }) })
    return () => { alive = false }
  }, [wordId, load])

  const options = found?.wordId === wordId ? found.options : null

  if (options?.length === 0) return null
  return (
    <div className={css.pictureSuggestionsBlock}>
      <p className={css.pictureSuggestionsLabel}>Suggested pictures · click to add</p>
      <div className={css.pictureSuggestions}>
        {(options ?? PLACEHOLDERS).map((option, i) => option
          ? (
              <button key={option.url} type="button" className={css.pictureSuggestion} disabled={applying} title="Use this picture" onClick={() => void review.applyImage(candidate.phrase_id, option.url)}>
                <img src={option.url} alt="" onError={hideBrokenTile} />
                <span className={css.pictureSuggestionAdd}><Icon as={Plus} /></span>
              </button>
            )
          : <span key={i} className={css.pictureSuggestion} />)}
      </div>
    </div>
  )
}
