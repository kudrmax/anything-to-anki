import type { SortOrder } from '@/lib/preferences'
import { IconButton, Menu } from '@/ui'
import { SORT_ICON, sortItems, sortLabel } from './sortItems'

export function SortMenu({ value, onChange }: { value: SortOrder; onChange: (order: SortOrder) => void }) {
  return (
    <Menu
      items={sortItems(value, onChange)}
      trigger={<IconButton icon={SORT_ICON[value]} label={`Sort: ${sortLabel(value)}`} />}
    />
  )
}
