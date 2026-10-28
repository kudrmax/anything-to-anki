import type { CSSProperties, PointerEvent } from 'react'
import { Columns3, Minus, Monitor, Smartphone, X } from 'lucide-react'
import type { ColumnWidth } from '@/api/types'
import type { DragItem } from '@/cardLayout'
import { Button, Chip, Icon, IconButton, Select, Text } from '@/ui'
import { BlockPanel } from './BlockPanel'
import { ELEMENT_LABEL, WIDTH_OPTIONS } from './labels'
import { EDITOR_WINDOW_ATTR, TRAY_ATTR } from './layoutDrag'
import { SAMPLE_PARTS, type SamplePart } from './sampleParts'
import type { CardLayoutEditor } from './useCardLayoutEditor'
import { useFloatingWindow } from './useFloatingWindow'
import css from './cardLayoutEditor.module.css'

interface EditorWindowProps {
  editor: CardLayoutEditor
  /** Что есть у карточки образца. */
  parts: ReadonlySet<SamplePart>
  onTogglePart: (part: SamplePart) => void
  startDrag: (item: DragItem) => (e: PointerEvent) => void
  /** Над окном скрытых тянут блок или линию: отпустить — спрятать. */
  trayActive: boolean
  phone: boolean
  onTogglePhone: () => void
  onDone: () => void
}

/** Окно поверх экрана ревью: выбранный блок, скрытые блоки, колонки. */
export function EditorWindow({ editor, parts, onTogglePart, startDrag, trayActive, phone, onTogglePhone, onDone }: EditorWindowProps) {
  const { view, selection, select, edit, editAndDeselect } = editor
  const { offset, startMove } = useFloatingWindow()
  if (!view) return null
  const { columns } = view.layout

  return (
    <aside {...{ [EDITOR_WINDOW_ATTR]: '' }} className={css.window} style={{ '--wx': `${offset.x}px`, '--wy': `${offset.y}px` } as CSSProperties}>
      <div className={css.windowHead} onPointerDown={startMove}>
        <p className={css.windowTitle}>Card layout</p>
        <IconButton
          icon={phone ? Monitor : Smartphone}
          label={phone ? 'Show the desktop review' : 'Show the phone review'}
          onClick={onTogglePhone}
        />
        <IconButton icon={X} label="Close the card layout editor" onClick={onDone} />
      </div>

      <div className={css.windowBody}>
        {!phone && (
          <div className={css.section}>
            <p className={css.sectionLabel}>Sample card has</p>
            <div className={css.trayItems}>
              {SAMPLE_PARTS.map(({ part, label }) => (
                <Chip key={part} small on={parts.has(part)} onClick={() => onTogglePart(part)}>{label}</Chip>
              ))}
            </div>
          </div>
        )}

        {!phone && (
          <div {...{ [TRAY_ATTR]: '' }} className={trayActive ? `${css.tray} ${css.trayActive}` : css.tray}>
            <p className={css.sectionLabel}>Hidden blocks</p>
            <div className={css.trayItems}>
              {view.hidden.map(element => (
                <button
                  key={element}
                  type="button"
                  className={selection?.kind === 'block' && selection.element === element ? `${css.trayItem} ${css.selected}` : css.trayItem}
                  onPointerDown={startDrag({ kind: 'block', element, placed: false })}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') select({ kind: 'block', element }) }}
                >
                  {ELEMENT_LABEL[element]}
                </button>
              ))}
              {view.hidden.length === 0 && <span className={css.trayEmpty}>Drag a block here to hide it.</span>}
            </div>
            <p className={css.sectionLabel}>Add</p>
            <div className={css.trayItems}>
              <button type="button" className={css.trayItem} onPointerDown={startDrag({ kind: 'new-divider' })}>
                <Icon as={Minus} size="s" />Divider
              </button>
            </div>
          </div>
        )}

        {phone
          ? <p className={css.hint}>This is the review on a phone. Change the layout on the desktop review.</p>
          : selection
            ? <BlockPanel view={view} selection={selection} edit={change => void edit(change)} editAndDeselect={change => void editAndDeselect(change)} />
            : <p className={css.hint}>Drag blocks on the card to arrange it. Click a block to change how it looks.</p>}

        {!phone && (
          <>
            <div className={css.section}>
              <p className={css.sectionLabel}>Columns</p>
              {columns.map((column, c) => (
                <div key={c} className={css.columnRow}>
                  <span className={css.columnName}>Column {c + 1}</span>
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
              {view.can_add_column && (
                <Button variant="link" onClick={() => void edit({ kind: 'add_column' })}><Icon as={Columns3} size="s" />Add column</Button>
              )}
            </div>

            <div className={css.windowActions}>
              <Button variant="link" onClick={() => void editAndDeselect({ kind: 'reset' })}>Reset to default</Button>
            </div>
          </>
        )}
        {editor.error && <Text tone="err">{editor.error}</Text>}
      </div>
    </aside>
  )
}
