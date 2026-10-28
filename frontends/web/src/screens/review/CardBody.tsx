import { ChevronDown, ChevronUp } from 'lucide-react'
import type { CardLayoutRow, CardLayoutView } from '@/api/types'
import {
  BLOCK_ATTR, CARD_ELEMENTS, COLUMN_ATTR, CardBlock, ROW_ATTR, ROW_KIND_ATTR, inRowOrder, isEmptyBlock, isSelectedBlock,
  isSelectedDivider, selectOnKey, useCardLayoutEditing, type CardBlockContext, type CardLayoutEditing, type DragItem,
} from '@/cardLayout'
import { Icon } from '@/ui'
import layoutCss from '@/cardLayout/cardLayout.module.css'
import editable from '@/cardLayout/editable.module.css'
import { VIEW_CONTROL } from './viewControl'
import css from './review.module.css'

interface CardBodyProps {
  view: CardLayoutView
  ctx: CardBlockContext
  detailsOpen: boolean
  onToggleDetails: () => void
}

interface RowProps {
  row: CardLayoutRow
  column: number
  index: number
  view: CardLayoutView
  ctx: CardBlockContext
  editing: CardLayoutEditing | null
}

/** Что делает блок или линия в редакторе раскладки: выбирается, тянется, подсвечивается. */
function editableProps(editing: CardLayoutEditing, item: DragItem, label: string, selected: boolean, dragged: boolean) {
  const classes = [editing.dragged && editable.grabbing, selected && editable.selected, dragged && editable.dragged]
  return {
    role: 'button',
    tabIndex: 0,
    'aria-label': label,
    'aria-pressed': selected,
    classes: classes.filter(Boolean).join(' '),
    onPointerDown: editing.startDrag(item),
    onKeyDown: selectOnKey(editing, item),
  }
}

function Row({ row, column, index, view, ctx, editing }: RowProps) {
  const rowAttrs = editing ? { [ROW_ATTR]: index, [ROW_KIND_ATTR]: row.kind } : {}
  if (row.kind === 'divider') {
    if (!editing) return <hr className={layoutCss.divider} />
    const item: DragItem = { kind: 'divider', column, row: index }
    const { classes, ...props } = editableProps(editing, item, 'Divider', isSelectedDivider(editing.selection, column, index), false)
    return <hr {...rowAttrs} {...props} className={`${layoutCss.divider} ${editable.divider} ${classes}`} />
  }
  const blocks = inRowOrder(view, row.elements
    .map((element, position) => ({ element, position, content: CARD_ELEMENTS[element](ctx) }))
    .filter(({ content }) => !isEmptyBlock(content)))
  if (blocks.length === 0) return null
  return (
    <div className={layoutCss.row} {...rowAttrs}>
      {blocks.map(({ element, position, content }) => {
        if (!editing) return <CardBlock key={element} element={element} view={view}>{content}</CardBlock>
        const item: DragItem = { kind: 'block', element, placed: true }
        const dragged = editing.dragged?.kind === 'block' && editing.dragged.element === element
        const label = editing.labelOf(element)
        const { classes, ...props } = editableProps(editing, item, label, isSelectedBlock(editing.selection, element), dragged)
        return (
          <CardBlock key={element} element={element} view={view} {...{ [BLOCK_ATTR]: position }} {...props} className={`${editable.block} ${classes}`}>
            {content}
            <span className={editable.label} aria-hidden>{label}</span>
          </CardBlock>
        )
      })}
    </div>
  )
}

/**
 * Тело карточки по раскладке пользователя. Первая колонка — то, по чему решаешь: на телефоне она видна сразу,
 * остальные колонки свёрнуты в строку Details. В редакторе раскладки блоки и линии ещё и выбираются и тянутся.
 */
export function CardBody({ view, ctx, detailsOpen, onToggleDetails }: CardBodyProps) {
  const editing = useCardLayoutEditing()
  const [first, ...rest] = view.layout.columns
  const columnAttrs = (column: number) => (editing ? { [COLUMN_ATTR]: column } : {})
  const columnClass = (base: string) => (editing ? `${base} ${editable.column}` : base)
  const rows = (column: typeof first, c: number) =>
    column.rows.map((row, i) => <Row key={i} row={row} column={c} index={i} view={view} ctx={ctx} editing={editing} />)
  return (
    <>
      <div
        className={columnClass(css.cardLeft)}
        {...columnAttrs(0)}
        ref={editing ? el => editing.setRoot(el?.parentElement ?? null) : undefined}
      >
        {rows(first, 0)}
      </div>
      <button type="button" className={css.detailsToggle} aria-expanded={detailsOpen} {...VIEW_CONTROL} onClick={onToggleDetails}>
        Details<Icon as={detailsOpen ? ChevronUp : ChevronDown} size="s" />
      </button>
      {rest.map((column, i) => (
        <div key={i} className={columnClass(detailsOpen ? css.cardRight : `${css.cardRight} ${css.collapsed}`)} {...columnAttrs(i + 1)}>
          {rows(column, i + 1)}
        </div>
      ))}
    </>
  )
}
