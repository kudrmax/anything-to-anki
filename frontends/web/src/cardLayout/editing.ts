import { createContext, useContext, type KeyboardEvent, type PointerEvent } from 'react'
import type { CardElement, CardLayoutView } from '@/api/types'

/** Что тянут: блок (с карточки или из скрытых), линию с карточки или новую линию. */
export type DragItem =
  | { kind: 'block'; element: CardElement; placed: boolean }
  | { kind: 'divider'; column: number; row: number }
  | { kind: 'new-divider' }

/** Выбранное на карточке: блок или линия. */
export type LayoutSelection = { kind: 'block'; element: CardElement } | { kind: 'divider'; column: number; row: number }

/** Метки, по которым редактор находит колонки, строки и блоки карточки под указателем. */
export const COLUMN_ATTR = 'data-column'
export const ROW_ATTR = 'data-row'
export const ROW_KIND_ATTR = 'data-row-kind'
export const BLOCK_ATTR = 'data-position'

/** Редактор раскладки поверх карточки: что выбрано и тянется, как начать тянуть и выбрать. */
export interface CardLayoutEditing {
  selection: LayoutSelection | null
  dragged: DragItem | null
  startDrag: (item: DragItem) => (e: PointerEvent) => void
  select: (item: DragItem) => void
  /** Название блока: его подпись при наведении. */
  labelOf: (element: CardElement) => string
  /** Карточка, внутри которой лежат колонки: от неё редактор считает, куда бросают. */
  setRoot: (root: HTMLElement | null) => void
}

/** Есть только в редакторе раскладки; на ревью карточка о нём не знает. */
export const CardLayoutEditingContext = createContext<CardLayoutEditing | null>(null)
export const useCardLayoutEditing = (): CardLayoutEditing | null => useContext(CardLayoutEditingContext)

/** Раскладка, которую карточка показывает вместо сохранённой: в редакторе — та, что сейчас правят. */
export const CardLayoutViewContext = createContext<CardLayoutView | null | undefined>(undefined)

export const isSelectedBlock = (selection: LayoutSelection | null, element: CardElement): boolean =>
  selection?.kind === 'block' && selection.element === element

export const isSelectedDivider = (selection: LayoutSelection | null, column: number, row: number): boolean =>
  selection?.kind === 'divider' && selection.column === column && selection.row === row

/** Enter и пробел выбирают блок или линию с клавиатуры. */
export const selectOnKey = (editing: CardLayoutEditing, item: DragItem) => (e: KeyboardEvent) => {
  if (e.key !== 'Enter' && e.key !== ' ') return
  e.preventDefault()
  editing.select(item)
}
