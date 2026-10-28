import { ChevronDown, ChevronUp } from 'lucide-react'
import type { CardLayoutRow, CardLayoutView } from '@/api/types'
import { CARD_ELEMENTS, CardBlock, inRowOrder, isEmptyBlock, type CardBlockContext } from '@/cardLayout'
import { Icon } from '@/ui'
import layoutCss from '@/cardLayout/cardLayout.module.css'
import css from './review.module.css'

interface CardBodyProps {
  view: CardLayoutView
  ctx: CardBlockContext
  detailsOpen: boolean
  onToggleDetails: () => void
}

function Row({ row, view, ctx }: { row: CardLayoutRow; view: CardLayoutView; ctx: CardBlockContext }) {
  if (row.kind === 'divider') return <hr className={layoutCss.divider} />
  const blocks = inRowOrder(view, row.elements
    .map(element => ({ element, content: CARD_ELEMENTS[element](ctx) }))
    .filter(({ content }) => !isEmptyBlock(content)))
  if (blocks.length === 0) return null
  return (
    <div className={layoutCss.row}>
      {blocks.map(({ element, content }) => <CardBlock key={element} element={element} view={view}>{content}</CardBlock>)}
    </div>
  )
}

/**
 * Тело карточки по раскладке пользователя. Первая колонка — то, по чему решаешь: на телефоне она видна сразу,
 * остальные колонки свёрнуты в строку Details.
 */
export function CardBody({ view, ctx, detailsOpen, onToggleDetails }: CardBodyProps) {
  const [first, ...rest] = view.layout.columns
  const rows = (column: typeof first) => column.rows.map((row, i) => <Row key={i} row={row} view={view} ctx={ctx} />)
  return (
    <>
      <div className={css.cardLeft}>{rows(first)}</div>
      <button type="button" className={css.detailsToggle} aria-expanded={detailsOpen} onClick={onToggleDetails}>
        Details<Icon as={detailsOpen ? ChevronUp : ChevronDown} size="s" />
      </button>
      {rest.map((column, i) => (
        <div key={i} className={detailsOpen ? css.cardRight : `${css.cardRight} ${css.collapsed}`}>{rows(column)}</div>
      ))}
    </>
  )
}
