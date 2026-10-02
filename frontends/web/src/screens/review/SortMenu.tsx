import { ArrowDownWideNarrow, ListOrdered, type LucideIcon } from 'lucide-react'
import type { SortOrder } from '@/lib/preferences'
import { IconButton, Menu } from '@/ui'

const SORT_LABEL: Record<SortOrder, string> = { relevance: 'Relevance', chronological: 'Text order' }
const SORT_ICON: Record<SortOrder, LucideIcon> = { relevance: ArrowDownWideNarrow, chronological: ListOrdered }
const SORT_ORDERS: SortOrder[] = ['relevance', 'chronological']

export function SortMenu({ value, onChange }: { value: SortOrder; onChange: (order: SortOrder) => void }) {
  return (
    <Menu
      items={SORT_ORDERS.map(order => ({ label: SORT_LABEL[order], selected: order === value, onSelect: () => onChange(order) }))}
      trigger={<IconButton icon={SORT_ICON[value]} label={`Sort: ${SORT_LABEL[value]}`} />}
    />
  )
}
