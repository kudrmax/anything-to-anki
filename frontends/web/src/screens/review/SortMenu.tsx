import { ChevronDown } from 'lucide-react'
import type { SortOrder } from '@/lib/preferences'
import { Button, Icon, Menu } from '@/ui'

const SORT_LABEL: Record<SortOrder, string> = { relevance: 'Relevance', chronological: 'Text order' }
const SORT_ORDERS: SortOrder[] = ['relevance', 'chronological']

export function SortMenu({ value, onChange }: { value: SortOrder; onChange: (order: SortOrder) => void }) {
  return (
    <Menu
      items={SORT_ORDERS.map(order => ({ label: SORT_LABEL[order], selected: order === value, onSelect: () => onChange(order) }))}
      trigger={
        <Button variant="link" title="Sort phrases">
          {SORT_LABEL[value]}
          <Icon as={ChevronDown} size="s" />
        </Button>
      }
    />
  )
}
