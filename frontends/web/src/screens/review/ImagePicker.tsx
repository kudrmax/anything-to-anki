import { useEffect, useRef, useState, type FormEvent, type SyntheticEvent } from 'react'
import type { ImageOption, ImageProvider, StoredCandidate } from '@/api/types'
import { highlightParts } from '@/lib/text/meaning'
import { Button, Empty, Field, Modal, Spinner } from '@/ui'
import phrase from '@/ui/phrase.module.css'
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

/**
 * Окно выбора картинки target'а: выбранная встаёт на карточку вместо текущей.
 * Сразу ищет по target'у; запрос можно уточнить, если у слова несколько значений.
 */
export function ImagePicker({ candidate, review, onClose }: ImagePickerProps) {
  const [query, setQuery] = useState(candidate.lemma)
  const [options, setOptions] = useState<ImageOption[] | null>(null)
  const [failed, setFailed] = useState(false)
  const latestSearch = useRef(0)
  const { findImages, applyImage } = review
  const applying = review.busy.image.has(candidate.id)

  const search = async (text?: string) => {
    const searchId = ++latestSearch.current
    setOptions(null)
    setFailed(false)
    const found = await findImages(candidate.id, text)
    if (searchId !== latestSearch.current) return
    if (!found) {
      setFailed(true)
      return
    }
    setQuery(found.query)
    setOptions(found.options)
  }

  useEffect(() => {
    void search()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- первый поиск — один раз на открытие окна
  }, [candidate.id])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void search(query)
  }

  const pick = async (url: string) => {
    await applyImage(candidate.id, url)
    onClose()
  }

  return (
    <Modal title={`Picture for “${candidate.lemma}”`} onClose={onClose} footer={<Button onClick={onClose}>Cancel</Button>}>
      <p className={phrase.context}>
        {highlightParts(candidate.phrase, candidate.lemma, candidate.surface_form).map((part, i) =>
          part.target ? <b key={i} className={phrase.target}>{part.text}</b> : part.text,
        )}
      </p>
      <form className={css.imageSearch} onSubmit={submit}>
        <Field value={query} aria-label="Picture search" onChange={e => setQuery(e.target.value)} />
        <Button type="submit" disabled={options === null && !failed}>Search</Button>
      </form>
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
