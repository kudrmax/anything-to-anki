import { useCallback, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Columns3, Minus, X } from 'lucide-react'
import type { ColumnWidth } from '@/api/types'
import { columnTracks } from '@/cardLayout'
import { Button, Chip, Empty, Icon, IconButton, Select, Spinner, Text } from '@/ui'
import { BlockPanel } from './BlockPanel'
import { LayoutCanvas } from './LayoutCanvas'
import { ELEMENT_LABEL, WIDTH_OPTIONS } from './labels'
import { editFor, TRAY_ATTR, type DragItem, type DropTarget } from './layoutDrag'
import { ALL_SAMPLE_PARTS, SAMPLE_PARTS, sampleContext, type SamplePart } from './sampleCard'
import { useCardLayoutEditor } from './useCardLayoutEditor'
import { useLayoutDrag } from './useLayoutDrag'
import css from './cardLayoutEditor.module.css'

const dragLabel = (item: DragItem): string => item.kind === 'block' ? ELEMENT_LABEL[item.element] : 'Divider'

/**
 * Конструктор тела карточки ревью: блоки переставляются перетаскиванием по колонкам и строкам,
 * у выбранного блока меняются размер, цвет и выравнивание. Фраза и нижняя полоса не меняются.
 */
export function CardLayoutSection() {
  const editor = useCardLayoutEditor()
  const { view, selection, select, edit, editAndDeselect } = editor
  const canvasRef = useRef<HTMLDivElement>(null)
  const [parts, setParts] = useState(ALL_SAMPLE_PARTS)
  const ctx = useMemo(() => sampleContext(parts), [parts])
  const togglePart = (part: SamplePart) => setParts(current => {
    const next = new Set(current)
    if (!next.delete(part)) next.add(part)
    return next
  })

  const onClick = useCallback((item: DragItem) => {
    if (item.kind === 'block') select({ kind: 'block', element: item.element })
    else if (item.kind === 'divider') select({ kind: 'divider', column: item.column, row: item.row })
  }, [select])
  // Блок после броска остаётся выбранным; место линии после броска другое — выбор с неё снимается.
  const onDrop = useCallback((item: DragItem, target: DropTarget) => {
    const change = editFor(item, target)
    if (!change) return
    if (item.kind === 'block' && change.kind === 'move_block') {
      select({ kind: 'block', element: item.element })
      void edit(change)
    } else {
      void editAndDeselect(change)
    }
  }, [edit, editAndDeselect, select])
  const { drag, start } = useLayoutDrag(canvasRef, onDrop, onClick)

  if (!view) {
    return <Empty>{editor.error ? <Text tone="err">{editor.error}</Text> : <Spinner />}</Empty>
  }
  const { columns } = view.layout

  return (
    <>
      <p className={css.hint}>
        Drag blocks to arrange the card. Drop a block next to another to put them in one row.
        Click a block to change its size and colour. The phrase and the bottom bar stay in place.
      </p>
      <div className={css.editor}>
        <div className={css.main}>
          <div className={css.sampleBar}>
            <span className={css.sampleLabel}>Sample card has</span>
            {SAMPLE_PARTS.map(({ part, label }) => (
              <Chip key={part} small on={parts.has(part)} onClick={() => togglePart(part)}>{label}</Chip>
            ))}
          </div>
          <div className={css.columnBar} style={{ '--card-cols': columnTracks(columns) } as CSSProperties}>
            {columns.map((column, c) => (
              <div key={c} className={css.columnTools}>
                <Select
                  aria-label={`Column ${c + 1} width`}
                  className={css.widthSelect}
                  value={column.width}
                  onChange={e => void edit({ kind: 'resize_column', column: c, width: e.target.value as ColumnWidth })}
                >
                  {WIDTH_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </Select>
                {view.can_remove_column && (
                  <IconButton icon={X} label={`Remove column ${c + 1}`} onClick={() => void editAndDeselect({ kind: 'remove_column', column: c })} />
                )}
              </div>
            ))}
          </div>
          <LayoutCanvas
            view={view}
            ctx={ctx}
            rootRef={canvasRef}
            drag={drag}
            selection={selection}
            startDrag={start}
            onSelect={onClick}
            onDeselect={() => select(null)}
          />
        </div>

        <aside className={css.side}>
          {selection
            ? <BlockPanel view={view} selection={selection} edit={change => void edit(change)} editAndDeselect={change => void editAndDeselect(change)} />
            : <p className={css.panelHint}>Click a block on the card to change how it looks.</p>}

          <div {...{ [TRAY_ATTR]: '' }} className={drag?.target?.kind === 'tray' ? `${css.tray} ${css.trayActive}` : css.tray}>
            <p className={css.trayLabel}>Hidden blocks</p>
            <div className={css.trayItems}>
              {view.hidden.map(element => (
                <button
                  key={element}
                  type="button"
                  className={selection?.kind === 'block' && selection.element === element ? `${css.trayItem} ${css.selected}` : css.trayItem}
                  onPointerDown={start({ kind: 'block', element, placed: false })}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick({ kind: 'block', element, placed: false }) }}
                >
                  {ELEMENT_LABEL[element]}
                </button>
              ))}
              {view.hidden.length === 0 && <span className={css.trayEmpty}>Drag a block here to hide it.</span>}
            </div>
            <p className={css.trayLabel}>Add</p>
            <div className={css.trayItems}>
              <button type="button" className={css.trayItem} onPointerDown={start({ kind: 'new-divider' })}>
                <Icon as={Minus} size="s" />Divider
              </button>
            </div>
          </div>

          <div className={css.sideActions}>
            {view.can_add_column && (
              <Button variant="link" onClick={() => void edit({ kind: 'add_column' })}><Icon as={Columns3} size="s" />Add column</Button>
            )}
            <Button variant="link" onClick={() => void editAndDeselect({ kind: 'reset' })}>Reset to default</Button>
          </div>
          {editor.error && <Text tone="err">{editor.error}</Text>}
        </aside>
      </div>

      {drag && (
        <span className={css.ghost} style={{ '--gx': `${drag.x}px`, '--gy': `${drag.y}px` } as CSSProperties}>
          {dragLabel(drag.item)}
        </span>
      )}
    </>
  )
}
