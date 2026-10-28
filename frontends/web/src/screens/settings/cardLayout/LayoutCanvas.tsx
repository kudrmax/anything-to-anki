import { Fragment, type CSSProperties, type KeyboardEvent, type PointerEvent, type RefObject } from 'react'
import { ChevronUp } from 'lucide-react'
import type { CardElement, CardLayoutRow, CardLayoutView } from '@/api/types'
import { CARD_ELEMENTS, CardBlock, columnTracks, isEmptyBlock, type CardBlockContext } from '@/cardLayout'
import { phraseParts } from '@/lib/text/phraseParts'
import { Button, Icon } from '@/ui'
import { BLOCK_ATTR, COLUMN_ATTR, ROW_ATTR, ROW_KIND_ATTR, type DragItem } from './layoutDrag'
import { ELEMENT_LABEL } from './labels'
import { SAMPLE_CARD } from './sampleCard'
import type { LayoutDrag } from './useLayoutDrag'
import type { LayoutSelection } from './useCardLayoutEditor'
import layoutCss from '@/cardLayout/cardLayout.module.css'
import phrase from '@/ui/phrase.module.css'
import css from './cardLayoutEditor.module.css'

const DECISIONS = ['Learn', 'Cloze', 'Know', 'Skip']

interface LayoutCanvasProps {
  view: CardLayoutView
  /** Образец карточки, который показывает превью. */
  ctx: CardBlockContext
  rootRef: RefObject<HTMLDivElement | null>
  drag: LayoutDrag | null
  selection: LayoutSelection | null
  startDrag: (item: DragItem) => (e: PointerEvent) => void
  /** Выбор с клавиатуры: Enter или пробел на блоке или линии. */
  onSelect: (item: DragItem) => void
  onDeselect: () => void
}

const isSelectedBlock = (selection: LayoutSelection | null, element: CardElement) =>
  selection?.kind === 'block' && selection.element === element

const isSelectedDivider = (selection: LayoutSelection | null, column: number, row: number) =>
  selection?.kind === 'divider' && selection.column === column && selection.row === row

const isDragged = (drag: LayoutDrag | null, element: CardElement) =>
  drag?.item.kind === 'block' && drag.item.element === element

/** Превью карточки на образце: фраза и нижняя полоса стоят на месте, тело собирается перетаскиванием. */
export function LayoutCanvas({ view, ctx, rootRef, drag, selection, startDrag, onSelect, onDeselect }: LayoutCanvasProps) {
  const onKey = (item: DragItem) => (e: KeyboardEvent) => {
    if (e.key !== 'Enter' && e.key !== ' ') return
    e.preventDefault()
    onSelect(item)
  }
  const row = (column: number, rowIndex: number, cardRow: CardLayoutRow) => {
    const rowAttrs = { [ROW_ATTR]: rowIndex, [ROW_KIND_ATTR]: cardRow.kind }
    if (cardRow.kind === 'divider') {
      const selected = isSelectedDivider(selection, column, rowIndex)
      return (
        <div
          key={rowIndex}
          {...rowAttrs}
          role="button"
          tabIndex={0}
          aria-label="Divider"
          aria-pressed={selected}
          className={selected ? `${css.divider} ${css.selected}` : css.divider}
          onPointerDown={startDrag({ kind: 'divider', column, row: rowIndex })}
          onKeyDown={onKey({ kind: 'divider', column, row: rowIndex })}
        >
          <hr className={layoutCss.divider} />
        </div>
      )
    }
    // Превью показывает ровно то, что показала бы карточка: блока, которому образцу нечего показать, нет, как и на ревью.
    const blocks = cardRow.elements
      .map((element, position) => ({ element, position, content: CARD_ELEMENTS[element](ctx) }))
      .filter(({ content }) => !isEmptyBlock(content))
    if (blocks.length === 0) return null
    return (
      <div key={rowIndex} {...rowAttrs} className={layoutCss.row}>
        {blocks.map(({ element, position, content }) => {
          const classes = [css.block, isSelectedBlock(selection, element) && css.selected, isDragged(drag, element) && css.dragged]
          return (
            <CardBlock
              key={element}
              element={element}
              view={view}
              {...{ [BLOCK_ATTR]: position }}
              role="button"
              tabIndex={0}
              aria-label={ELEMENT_LABEL[element]}
              aria-pressed={isSelectedBlock(selection, element)}
              className={classes.filter(Boolean).join(' ')}
              onPointerDown={startDrag({ kind: 'block', element, placed: true })}
              onKeyDown={onKey({ kind: 'block', element, placed: true })}
            >
              {content}
              <span className={css.blockLabel} aria-hidden>{ELEMENT_LABEL[element]}</span>
            </CardBlock>
          )
        })}
      </div>
    )
  }

  const target = drag?.target
  const line = target && target.kind !== 'tray' ? target.line : null

  return (
    <div
      ref={rootRef}
      className={drag ? `${css.frame} ${css.dragging}` : css.frame}
      style={{ '--card-cols': columnTracks(view.layout.columns) } as CSSProperties}
      onPointerDown={onDeselect}
    >
      <div className={css.fixedHead}>
        <p className={css.phrase}>
          {phraseParts(SAMPLE_CARD.phrase).map((part, i) =>
            part.target ? <b key={i} className={`${phrase.target} ${phrase.targetCurrent}`}>{part.text}</b> : part.text)}
        </p>
      </div>
      {view.layout.columns.map((column, c) => (
        <Fragment key={c}>
          {c === 1 && <div className={css.details} aria-hidden>Details<Icon as={ChevronUp} size="s" /></div>}
          <div {...{ [COLUMN_ATTR]: c }} className={css.column}>
            {column.rows.map((cardRow, r) => row(c, r, cardRow))}
          </div>
        </Fragment>
      ))}
      <div className={css.fixedFoot}>
        {DECISIONS.map(label => <Button key={label} tabIndex={-1} variant={label === 'Learn' ? 'fill' : 'soft'}>{label}</Button>)}
      </div>
      {line && (
        <span
          className={css.dropLine}
          style={{ '--x': `${line.x}px`, '--y': `${line.y}px`, '--w': `${line.width}px`, '--hh': `${line.height}px` } as CSSProperties}
        />
      )}
    </div>
  )
}
