import type { CardElement, CardLayoutEdit } from '@/api/types'
import { BLOCK_ATTR, COLUMN_ATTR, ROW_ATTR, ROW_KIND_ATTR, type DragItem } from '@/cardLayout'

/** Линия, куда встанет брошенное, — в координатах окна. */
export interface Line { x: number; y: number; width: number; height: number }

/** Куда отпустят: новая строка перед строкой `row`, место в строке `row` или лоток скрытых. */
export type DropTarget =
  | { kind: 'gap'; column: number; row: number; line: Line }
  | { kind: 'join'; column: number; row: number; position: number; line: Line }
  | { kind: 'tray' }

/** Отступ от края строки блоков, в котором блок встаёт новой строкой, а не в эту. */
const ROW_EDGE = 8
const LINE = 2

export const TRAY_ATTR = 'data-tray'
export const EDITOR_WINDOW_ATTR = 'data-layout-window'

/** Правка раскладки, которую делает бросок; null — бросок ничего не меняет. */
export function editFor(item: DragItem, target: DropTarget): CardLayoutEdit | null {
  if (item.kind === 'block') {
    if (target.kind === 'tray') return item.placed ? { kind: 'hide_block', element: item.element } : null
    const position = target.kind === 'join' ? target.position : null
    return { kind: 'move_block', element: item.element, column: target.column, row: target.row, position }
  }
  if (item.kind === 'divider') {
    if (target.kind === 'tray') return { kind: 'remove_divider', column: item.column, row: item.row }
    if (target.kind !== 'gap') return null
    return { kind: 'move_row', column: item.column, row: item.row, to_column: target.column, to_row: target.row }
  }
  return target.kind === 'gap' ? { kind: 'insert_divider', column: target.column, row: target.row } : null
}

const inside = (rect: DOMRect, x: number, y: number) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom

const childrenWith = (parent: Element, attr: string): HTMLElement[] =>
  Array.from(parent.querySelectorAll<HTMLElement>(`:scope > [${attr}]`))

/** Место в строке блоков: перед первым блоком той же линии, правее середины которого указатель. */
function joinAt(row: HTMLElement, x: number, y: number): { position: number; line: Line } {
  // Место берётся из самого блока: пустые блоки не рисуются, а прижатые вправо стоят в конце строки.
  const blocks = childrenWith(row, BLOCK_ATTR)
    .map(block => ({ rect: block.getBoundingClientRect(), position: Number(block.getAttribute(BLOCK_ATTR)) }))
  const onLine = blocks.filter(({ rect }) => y >= rect.top && y <= rect.bottom)
  const line = onLine.length > 0 ? onLine : blocks.slice(-1)
  const before = line.find(({ rect }) => x < rect.left + rect.width / 2)
  const edge = before ?? line[line.length - 1]
  const lineX = before ? edge.rect.left : edge.rect.right
  return {
    position: before ? before.position : edge.position + 1,
    line: { x: lineX - LINE / 2, y: edge.rect.top, width: LINE, height: edge.rect.height },
  }
}

/** Промежуток между строками колонки, ближайший к указателю. */
function gapAt(column: HTMLElement, y: number): { row: number; line: Line } {
  const area = column.getBoundingClientRect()
  const rows = childrenWith(column, ROW_ATTR).map(row => row.getBoundingClientRect())
  const row = rows.filter(rect => rect.top + rect.height / 2 < y).length
  const above = rows[row - 1]
  const below = rows[row]
  const lineY = above && below ? (above.bottom + below.top) / 2 : above ? above.bottom + LINE * 2 : below ? below.top - LINE * 2 : area.top + LINE * 4
  const style = getComputedStyle(column)
  const left = area.left + parseFloat(style.paddingLeft)
  const right = area.right - parseFloat(style.paddingRight)
  return { row, line: { x: left, y: lineY - LINE / 2, width: right - left, height: LINE } }
}

/** Куда упадёт то, что тянут, если отпустить в точке (x, y). */
export function findTarget(
  root: HTMLElement, item: DragItem, x: number, y: number, canHide: (element: CardElement) => boolean,
): DropTarget | null {
  const under = document.elementFromPoint(x, y)
  if (under?.closest(`[${TRAY_ATTR}]`)) {
    const keeps = item.kind === 'new-divider' || (item.kind === 'block' && (!item.placed || !canHide(item.element)))
    return keeps ? null : { kind: 'tray' }
  }
  const column = childrenWith(root, COLUMN_ATTR).find(c => inside(c.getBoundingClientRect(), x, y))
  if (!column) return null
  const columnIndex = Number(column.getAttribute(COLUMN_ATTR))
  if (item.kind === 'block') {
    const row = childrenWith(column, ROW_ATTR).find(r => {
      const rect = r.getBoundingClientRect()
      const edge = Math.min(ROW_EDGE, rect.height / 4)
      return r.getAttribute(ROW_KIND_ATTR) === 'blocks' && inside(rect, x, y) && y > rect.top + edge && y < rect.bottom - edge
    })
    if (row) return { kind: 'join', column: columnIndex, row: Number(row.getAttribute(ROW_ATTR)), ...joinAt(row, x, y) }
  }
  return { kind: 'gap', column: columnIndex, ...gapAt(column, y) }
}
