import { ChevronDown } from 'lucide-react'
import type { SourceGrouping, SourceSort } from '@/api/types'
import { Icon, Menu, type MenuItem } from '@/ui'
import type { SourceOrder } from './useSourceOrder'
import css from './sources.module.css'

const GROUPING_LABEL: Record<SourceGrouping, string> = { stage: 'By status', none: 'None' }
const SORT_LABEL: Record<SourceSort, string> = { added: 'Date added', name: 'Name', last_studied: 'Last studied' }
const GROUPINGS: SourceGrouping[] = ['stage', 'none']
const SORTS: SourceSort[] = ['added', 'name', 'last_studied']

function items<T extends string>(options: T[], labels: Record<T, string>, value: T, onChange: (option: T) => void): MenuItem[] {
  return options.map(option => ({ label: labels[option], selected: option === value, onSelect: () => onChange(option) }))
}

function OrderMenu({ name, value, items: menuItems }: { name: string; value: string; items: MenuItem[] }) {
  return (
    <Menu
      align="start"
      items={menuItems}
      trigger={
        <button type="button" className={css.orderTrigger}>
          {name}: <span className={css.orderValue}>{value}</span>
          <Icon as={ChevronDown} size="s" />
        </button>
      }
    />
  )
}

interface SourceOrderBarProps {
  order: SourceOrder
  onGrouping: (grouping: SourceGrouping) => void
  onSort: (sort: SourceSort) => void
}

/** Группировка и сортировка источников: тихая строка над списком, одна для всех областей. */
export function SourceOrderBar({ order, onGrouping, onSort }: SourceOrderBarProps) {
  return (
    <div className={css.orderBar}>
      <OrderMenu name="Group" value={GROUPING_LABEL[order.grouping]} items={items(GROUPINGS, GROUPING_LABEL, order.grouping, onGrouping)} />
      <OrderMenu name="Sort" value={SORT_LABEL[order.sort]} items={items(SORTS, SORT_LABEL, order.sort, onSort)} />
    </div>
  )
}
