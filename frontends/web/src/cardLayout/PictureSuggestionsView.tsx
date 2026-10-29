import type { SyntheticEvent } from 'react'
import { Plus } from 'lucide-react'
import type { ImageOption } from '@/api/types'
import { Icon } from '@/ui'
import css from './pictureSuggestions.module.css'

interface PictureSuggestionsViewProps {
  /** null — картинки ещё ищутся: на их месте пустые рамки. */
  options: ImageOption[] | null
  placeholders: number
  applying: boolean
  onPick: (url: string) => void
}

const hideBrokenTile = (e: SyntheticEvent<HTMLImageElement>) => {
  const tile = e.currentTarget.parentElement
  if (tile) tile.hidden = true
}

/** Подобранные картинки: клик ставит картинку, без клика ничего не сохраняется. */
export function PictureSuggestionsView({ options, placeholders, applying, onPick }: PictureSuggestionsViewProps) {
  return (
    <div className={css.block}>
      <p className={css.label}>Suggested pictures</p>
      <div className={css.grid}>
        {options
          ? options.map(option => (
              <button key={option.url} type="button" className={css.tile} disabled={applying} title="Use this picture" onClick={() => onPick(option.url)}>
                <img src={option.url} alt="" onError={hideBrokenTile} />
                <span className={css.add}><Icon as={Plus} /></span>
              </button>
            ))
          : Array.from({ length: placeholders }, (_, i) => <span key={i} className={css.tile} />)}
      </div>
    </div>
  )
}
