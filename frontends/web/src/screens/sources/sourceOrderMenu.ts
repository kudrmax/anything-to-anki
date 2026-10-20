import type { SourceGrouping, SourceSort, SourceSortDirection } from '@/api/types'
import type { MenuItem } from '@/ui'
import type { SourceOrder } from './useSourceOrder'

const GROUPING_LABEL: Record<SourceGrouping, string> = { stage: 'By status', none: 'None' }
const SORT_LABEL: Record<SourceSort, string> = { added: 'Date added', name: 'Name', last_studied: 'Last studied' }
const DIRECTION_LABEL: Record<SourceSort, Record<SourceSortDirection, string>> = {
  added: { forward: 'Newest first', reverse: 'Oldest first' },
  name: { forward: 'A → Z', reverse: 'Z → A' },
  last_studied: { forward: 'Newest first', reverse: 'Oldest first' },
}
const DIRECTIONS: SourceSortDirection[] = ['forward', 'reverse']
const GROUPINGS: SourceGrouping[] = ['stage', 'none']
const SORTS: SourceSort[] = ['added', 'name', 'last_studied']

function choices<T extends string>(options: T[], labels: Record<T, string>, value: T, onChange: (option: T) => void): MenuItem[] {
  return options.map(option => ({ label: labels[option], selected: option === value, onSelect: () => onChange(option) }))
}

export interface SourceOrderHandlers {
  onGrouping: (grouping: SourceGrouping) => void
  onSort: (sort: SourceSort) => void
  onDirection: (direction: SourceSortDirection) => void
}

/** Группировка и сортировка источников: два подменю в «…», один выбор для всех областей. */
export function sourceOrderItems(order: SourceOrder, { onGrouping, onSort, onDirection }: SourceOrderHandlers): MenuItem[] {
  const directions = DIRECTION_LABEL[order.sort]
  const directionItems = choices(DIRECTIONS, directions, order.direction, onDirection)
  return [
    { label: 'Group', value: GROUPING_LABEL[order.grouping], items: choices(GROUPINGS, GROUPING_LABEL, order.grouping, onGrouping) },
    {
      label: 'Sort',
      value: SORT_LABEL[order.sort],
      items: [
        ...choices(SORTS, SORT_LABEL, order.sort, onSort),
        ...directionItems.map((item, index) => (index === 0 ? { ...item, separated: true } : item)),
      ],
    },
  ]
}
