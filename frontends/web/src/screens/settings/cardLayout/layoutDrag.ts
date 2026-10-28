import type { CardElement, CardLayoutEdit } from '@/api/types'

/** Что тянут: блок (с карточки или из скрытых), линию с карточки или новую линию. */
export type DragItem =
  | { kind: 'block'; element: CardElement; placed: boolean }
  | { kind: 'divider'; column: number; row: number }
  | { kind: 'new-divider' }

export interface Line { x: number; y: number; width: number; height: number }

/** Куда отпустят: новая строка перед строкой `row`, место в строке `row` или лоток скрытых. */
export type DropTarget =
  | { kind: 'gap'; column: number; row: number; line: Line }
  | { kind: 'join'; column: number; row: number; position: number; line: Line }
  | { kind: 'tray' }

/** Отступ от края строки блоков, в котором блок встаёт новой строкой, а не в эту. */
const ROW_EDGE = 8
const LINE = 2

export const COLUMN_ATTR = 'data-column'
export const ROW_ATTR = 'data-row'
export const ROW_KIND_ATTR = 'data-row-kind'
export const BLOCK_ATTR = 'data-position'
export const TRAY_ATTR = 'data-tray'

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
function joinAt(root: DOMRect, row: HTMLElement, x: number, y: number): { position: number; line: Line } {
  const blocks = childrenWith(row, BLOCK_ATTR).map(block => block.getBoundingClientRect())
  const onLine = blocks.map((rect, i) => ({ rect, i })).filter(({ rect }) => y >= rect.top && y <= rect.bottom)
  const line = onLine.length > 0 ? onLine : blocks.map((rect, i) => ({ rect, i })).slice(-1)
  const before = line.find(({ rect }) => x < rect.left + rect.width / 2)
  const edge = before ?? line[line.length - 1]
  const lineX = before ? edge.rect.left : edge.rect.right
  return {
    position: before ? before.i : edge.i + 1,
    line: { x: lineX - root.left - LINE / 2, y: edge.rect.top - root.top, width: LINE, height: edge.rect.height },
  }
}

/** Промежуток между строками колонки, ближайший к указателю. */
function gapAt(root: DOMRect, column: HTMLElement, y: number): { row: number; line: Line } {
  const area = column.getBoundingClientRect()
  const rows = childrenWith(column, ROW_ATTR).map(row => row.getBoundingClientRect())
  const row = rows.filter(rect => rect.top + rect.height / 2 < y).length
  const above = rows[row - 1]
  const below = rows[row]
  const lineY = above && below ? (above.bottom + below.top) / 2 : above ? above.bottom + LINE * 2 : below ? below.top - LINE * 2 : area.top + LINE * 4
  const style = getComputedStyle(column)
  const left = area.left + parseFloat(style.paddingLeft)
  const right = area.right - parseFloat(style.paddingRight)
  return { row, line: { x: left - root.left, y: lineY - root.top - LINE / 2, width: right - left, height: LINE } }
}

/** Куда упадёт то, что тянут, если отпустить в точке (x, y). */
export function findTarget(root: HTMLElement, item: DragItem, x: number, y: number): DropTarget | null {
  const under = document.elementFromPoint(x, y)
  if (under?.closest(`[${TRAY_ATTR}]`)) return item.kind === 'new-divider' || (item.kind === 'block' && !item.placed) ? null : { kind: 'tray' }
  const rootRect = root.getBoundingClientRect()
  const column = childrenWith(root, COLUMN_ATTR).find(c => inside(c.getBoundingClientRect(), x, y))
  if (!column) return null
  const columnIndex = Number(column.getAttribute(COLUMN_ATTR))
  if (item.kind === 'block') {
    const row = childrenWith(column, ROW_ATTR).find(r => {
      const rect = r.getBoundingClientRect()
      const edge = Math.min(ROW_EDGE, rect.height / 4)
      return r.getAttribute(ROW_KIND_ATTR) === 'blocks' && inside(rect, x, y) && y > rect.top + edge && y < rect.bottom - edge
    })
    if (row) return { kind: 'join', column: columnIndex, row: Number(row.getAttribute(ROW_ATTR)), ...joinAt(rootRect, row, x, y) }
  }
  return { kind: 'gap', column: columnIndex, ...gapAt(rootRect, column, y) }
}
