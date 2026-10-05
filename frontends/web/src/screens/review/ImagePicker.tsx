import { useEffect, useState, type SyntheticEvent } from 'react'
import type { ImageOption, ImageProvider, StoredCandidate } from '@/api/types'
import { Button, Empty, Modal, Spinner } from '@/ui'
import type { Review } from './useReview'
import css from './review.module.css'

interface ImagePickerProps {
  candidate: StoredCandidate
  review: Review
  onClose: () => void
}

// Ссылка на картинку может умереть: такую плитку просто не показываем.
const hideBrokenTile = (e: SyntheticEvent<HTMLImageElement>) => {
  const tile = e.currentTarget.parentElement
  if (tile) tile.hidden = true
}

const PROVIDER_LABEL: Record<ImageProvider, string> = { wiktionary: 'Wiktionary', bing: 'Bing', yandex: 'Yandex' }

/** Окно выбора картинки target'а: выбранная встаёт на карточку вместо текущей. */
export function ImagePicker({ candidate, review, onClose }: ImagePickerProps) {
  const [options, setOptions] = useState<ImageOption[] | null>(null)
  const [failed, setFailed] = useState(false)
  const { findImages, applyImage } = review
  const applying = review.busy.image.has(candidate.id)

  useEffect(() => {
    let active = true
    void findImages(candidate.id).then(found => {
      if (!active) return
      if (found) setOptions(found)
      else setFailed(true)
    })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ищем один раз на открытие окна
  }, [candidate.id])

  const pick = async (url: string) => {
    await applyImage(candidate.id, url)
    onClose()
  }

  return (
    <Modal title={`Picture for “${candidate.lemma}”`} onClose={onClose} footer={<Button onClick={onClose}>Cancel</Button>}>
      {failed && <Empty>Picture search failed</Empty>}
      {!failed && options === null && <div className={css.status}><Spinner /> Searching…</div>}
      {options?.length === 0 && <Empty>No pictures found</Empty>}
      {options && options.length > 0 && (
        <div className={css.imageOptions}>
          {options.map(option => (
            <button key={option.url} type="button" className={css.imageOption} disabled={applying} onClick={() => void pick(option.url)}>
              <img src={option.url} alt="" loading="lazy" onError={hideBrokenTile} />
              {option.provider === 'wiktionary' && <span className={css.imageProvider}>{PROVIDER_LABEL[option.provider]}</span>}
            </button>
          ))}
        </div>
      )}
    </Modal>
  )
}
