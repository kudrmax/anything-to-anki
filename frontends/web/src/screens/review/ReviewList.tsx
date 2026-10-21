import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type HTMLAttributes, type ReactNode } from 'react'
import type { ReviewRow, StoredCandidate } from '@/api/types'
import { Button } from '@/ui'
import { fetchStart, isGap, listRows, rowIndexOf, rowsLoaded, type ReviewState } from './reviewState'
import { sectionToggleLabel } from './sections'
import { ROW_ESTIMATE_PX, ROWS_PER_FETCH } from './useReviewWindow'
import css from './review.module.css'

/** Заглушку начинают грузить за экран до того, как она покажется. */
const PREFETCH_MARGIN = '100% 0%'
const GAP_SELECTOR = '[data-gap-start]'
/** Дальше этого плавная прокрутка не идёт: переход к карточке — сразу. */
const SMOOTH_SCROLL_ROWS = 2 * ROWS_PER_FETCH

interface ReviewListProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onLoad'> {
  state: ReviewState
  /** true — строки пришли. */
  onLoad: (start: number, count: number) => Promise<boolean>
  renderCard: (card: StoredCandidate, current: boolean) => ReactNode
  onToggleSection: (row: ReviewRow) => void
  /** Смена — снова показать текущую карточку (например, список снова виден). */
  followKey?: unknown
}

/** Ближайший предок, который прокручивается: относительно него заглушка «рядом с экраном». */
function scrollParent(element: HTMLElement): HTMLElement | null {
  for (let node = element.parentElement; node; node = node.parentElement) {
    if (/(auto|scroll)/.test(getComputedStyle(node).overflowY)) return node
  }
  return null
}

/** Видимый список ревью: загруженные строки как есть, незагруженные — заглушками, которые грузятся у экрана. */
export function ReviewList({ state, onLoad, renderCard, onToggleSection, followKey, ...rest }: ReviewListProps) {
  const ref = useRef<HTMLDivElement>(null)
  const items = useMemo(() => listRows(state), [state])
  const [settled, setSettled] = useState(0)
  const { currentId, reviewId, version, cards } = state
  const currentIndex = rowIndexOf(state, currentId)

  // Текущая карточка в поле зрения. Плавно — только по загруженным строкам и недалеко: плавная прокрутка
  // сквозь заглушку грузила бы окна по пути и останавливалась не там. Открытие и дальний переход — сразу.
  // Перестроенный список (раскрыли раздел) не прокручивается: взгляд остаётся там, где был.
  const shown = useRef<{ reviewId: string | null; version: number; currentId: number | null; index: number | undefined; followKey: unknown } | null>(null)
  useLayoutEffect(() => {
    const before = shown.current
    const target = ref.current?.querySelector(`[data-candidate-id="${currentId}"]`)
    if (!target) return
    shown.current = { reviewId, version, currentId, index: currentIndex, followKey }
    if (before && before.reviewId === reviewId && before.currentId === currentId && before.followKey === followKey) return
    const smooth = before !== null && before.reviewId === reviewId && before.version === version
      && before.index !== undefined && currentIndex !== undefined
      && Math.abs(before.index - currentIndex) <= SMOOTH_SCROLL_ROWS && rowsLoaded(state, before.index, currentIndex)
    target.scrollIntoView({ block: 'nearest', behavior: smooth ? 'smooth' : 'auto' })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- прокручиваем при смене текущей, а не при каждой загрузке строк
  }, [reviewId, currentId, currentIndex, followKey])

  useEffect(() => {
    const container = ref.current
    if (!container || typeof IntersectionObserver === 'undefined') return
    const root = scrollParent(container)
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const gap = (entry.target as HTMLElement).dataset
        const start = Number(gap.gapStart)
        const end = Number(gap.gapEnd)
        const view = entry.rootBounds ?? { top: 0, bottom: window.innerHeight }
        const from = fetchStart(start, end, entry.boundingClientRect, view, ROWS_PER_FETCH)
        // Ответ мог устареть и не лечь: тогда заглушки проверяются ещё раз.
        void onLoad(from, Math.min(ROWS_PER_FETCH, end - from)).then(loaded => { if (loaded) setSettled(n => n + 1) })
      }
    }, { root, rootMargin: PREFETCH_MARGIN })
    container.querySelectorAll(GAP_SELECTOR).forEach(gap => observer.observe(gap))
    return () => observer.disconnect()
  }, [items, settled, onLoad])

  const gap = (start: number, end: number) => (
    <div
      key={`gap-${start}-${end}`}
      className={css.placeholder}
      data-gap-start={start}
      data-gap-end={end}
      style={{ '--placeholder-h': `${(end - start) * ROW_ESTIMATE_PX}px` } as CSSProperties}
      aria-hidden
    />
  )

  return (
    <div ref={ref} {...rest}>
      {items.map(item => {
        if (isGap(item)) return gap(item.start, item.end)
        if (item.kind === 'section') {
          return (
            <div key={`section-${item.index}`} className={css.sectionToggle}>
              <Button variant="link" onClick={() => onToggleSection(item)}>
                {item.section && sectionToggleLabel(item.section, item.count ?? 0, item.open ?? false)}
              </Button>
            </div>
          )
        }
        const card = item.phrase_id === null ? undefined : cards.get(item.phrase_id)
        if (!card) return gap(item.index, item.index + 1)
        return <Fragment key={card.phrase_id}>{renderCard(card, card.phrase_id === currentId)}</Fragment>
      })}
    </div>
  )
}
