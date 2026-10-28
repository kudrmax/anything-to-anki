import type { ReactNode } from 'react'
import type { BlockStyle, CardElement, CardElementKind, CardLayoutColumn, CardLayoutView } from '@/api/types'

export const styleOf = (view: CardLayoutView, element: CardElement): BlockStyle | undefined =>
  view.layout.styles.find(entry => entry.element === element)?.style

export const kindOf = (view: CardLayoutView, element: CardElement): CardElementKind | undefined =>
  view.elements.find(entry => entry.element === element)?.kind

/** Блок не рисуется, если элементу нечего показать. */
export const isEmptyBlock = (content: ReactNode): boolean =>
  content === null || content === undefined || content === false || content === ''

/** Порядок блоков строки на экране: прижатые вправо идут после остальных, вплотную друг к другу у правого края. */
export const inRowOrder = <T extends { element: CardElement }>(view: CardLayoutView, blocks: T[]): T[] =>
  [...blocks].sort((a, b) => Number(styleOf(view, a.element)?.align === 'end') - Number(styleOf(view, b.element)?.align === 'end'))

/** Ширины колонок — дорожки грида карточки. */
export const columnTracks = (columns: CardLayoutColumn[]): string =>
  columns.map(column => `minmax(0, var(--card-col-${column.width}))`).join(' ')
