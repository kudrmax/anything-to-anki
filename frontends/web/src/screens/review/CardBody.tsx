import { ChevronDown, ChevronUp } from 'lucide-react'
import type { CardLayoutView } from '@/api/types'
import {
  BLOCK_ATTR, COLUMN_ATTR, CardBlock, ROW_ATTR, ROW_KIND_ATTR, isSelectedBlock, isSelectedDivider, selectOnKey,
  useCardLayoutEditing, type CardLayoutEditing, type DragItem, type ShownColumn, type ShownRow,
} from '@/cardLayout'
import { Icon } from '@/ui'
import layoutCss from '@/cardLayout/cardLayout.module.css'
import editable from '@/cardLayout/editable.module.css'
import { VIEW_CONTROL } from './viewControl'
import css from './review.module.css'

interface CardBodyProps {
  view: CardLayoutView
  /** Что из раскладки карточка показывает: без пустых блоков, строк, колонок и лишних линий. */
  columns: ShownColumn[]
  detailsOpen: boolean
  onToggleDetails: () => void
}

interface RowProps {
  row: ShownRow
  column: number
  view: CardLayoutView
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

function Row({ row, column, view, editing }: RowProps) {
  const rowAttrs = editing ? { [ROW_ATTR]: row.index, [ROW_KIND_ATTR]: row.kind } : {}
  if (row.kind === 'divider') {
    if (!editing) return <hr className={layoutCss.divider} />
    const item: DragItem = { kind: 'divider', column, row: row.index }
    const { classes, ...props } = editableProps(editing, item, 'Divider', isSelectedDivider(editing.selection, column, row.index), false)
    return <hr {...rowAttrs} {...props} className={`${layoutCss.divider} ${editable.divider} ${classes}`} />
  }
  return (
    <div className={layoutCss.row} {...rowAttrs}>
      {row.blocks.map(({ element, position, content }) => {
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
export function CardBody({ view, columns, detailsOpen, onToggleDetails }: CardBodyProps) {
  const editing = useCardLayoutEditing()
  const [first, ...rest] = columns
  const columnAttrs = (column: ShownColumn) => (editing ? { [COLUMN_ATTR]: column.index } : {})
  const columnClass = (base: string) => (editing ? `${base} ${editable.column}` : base)
  const rows = (column: ShownColumn) =>
    column.rows.map(row => <Row key={row.index} row={row} column={column.index} view={view} editing={editing} />)
  return (
    <>
      <div
        className={columnClass(css.cardLeft)}
        {...columnAttrs(first)}
        ref={editing ? el => editing.setRoot(el?.parentElement ?? null) : undefined}
      >
        {rows(first)}
      </div>
      {rest.length > 0 && (
        <button type="button" className={css.detailsToggle} aria-expanded={detailsOpen} {...VIEW_CONTROL} onClick={onToggleDetails}>
          Details<Icon as={detailsOpen ? ChevronUp : ChevronDown} size="s" />
        </button>
      )}
      {rest.map(column => (
        <div key={column.index} className={columnClass(detailsOpen ? css.cardRight : `${css.cardRight} ${css.collapsed}`)} {...columnAttrs(column)}>
          {rows(column)}
        </div>
      ))}
    </>
  )
}
