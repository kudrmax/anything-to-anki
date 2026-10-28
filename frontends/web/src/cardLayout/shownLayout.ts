import type { ReactNode } from 'react'
import type { CardElement, CardLayoutView, ColumnWidth, DividerSticks } from '@/api/types'
import type { CardBlockContext } from './CardBlockContext'
import { CARD_ELEMENTS } from './cardElements'
import { inRowOrder, isEmptyBlock, styleOf } from './layoutView'

export interface ShownBlock {
  element: CardElement
  /** Место блока в строке раскладки: по нему редактор понимает, куда бросили. */
  position: number
  content: ReactNode
}

export type ShownRow =
  | { kind: 'divider'; index: number; sticks: DividerSticks }
  | { kind: 'blocks'; index: number; blocks: ShownBlock[] }

export interface ShownColumn {
  /** Номер колонки в раскладке. */
  index: number
  width: ColumnWidth
  rows: ShownRow[]
  /**
   * С какой строки всё уходит к низу колонки: с первой строки, где есть блок «Bottom», или с линии прямо над ней,
   * если линия прилипает к строке под ней.
   * Как «Right» прижимает блок к правому краю строки. null — к низу ничего не прижато.
   */
  bottomFrom: number | null
}

/**
 * Что карточка показывает из раскладки. Блок без содержимого не рисуется, строка без блоков — тоже.
 * Линия стоит только между видимыми строками: две подряд сливаются в одну, у края колонки её нет.
 * Колонка без видимых блоков не рисуется вовсе — кроме случая, когда пустые колонки нужны (в них бросают блок).
 */
export function shownColumns(view: CardLayoutView, ctx: CardBlockContext, keepEmptyColumns = false): ShownColumn[] {
  const columns = view.layout.columns.map((column, index): ShownColumn => {
    const rows: ShownRow[] = []
    let pendingDivider: ShownRow | null = null
    column.rows.forEach((row, rowIndex) => {
      if (row.kind === 'divider') {
        if (rows.length > 0) pendingDivider = { kind: 'divider', index: rowIndex, sticks: row.sticks }
        return
      }
      const blocks = inRowOrder(view, row.elements
        .map((element, position) => ({ element, position, content: CARD_ELEMENTS[element](ctx) }))
        .filter(({ content }) => !isEmptyBlock(content)))
      if (blocks.length === 0) return
      if (pendingDivider) rows.push(pendingDivider)
      pendingDivider = null
      rows.push({ kind: 'blocks', index: rowIndex, blocks })
    })
    const firstBottom = rows.findIndex(row => row.kind === 'blocks' && row.blocks.some(b => styleOf(view, b.element)?.valign === 'bottom'))
    const above = rows[firstBottom - 1]
    const lineGoesDown = above?.kind === 'divider' && above.sticks === 'below'
    const bottomFrom = firstBottom < 0 ? null : lineGoesDown ? firstBottom - 1 : firstBottom
    return { index, width: column.width, rows, bottomFrom }
  })
  const shown = keepEmptyColumns ? columns : columns.filter(column => column.rows.length > 0)
  // Совсем пустой карточке остаётся первая колонка: телу карточки и редактору нужна хотя бы одна.
  return shown.length > 0 ? shown : columns.slice(0, 1)
}
