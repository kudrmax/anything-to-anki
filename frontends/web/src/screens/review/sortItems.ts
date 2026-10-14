import { ArrowDownWideNarrow, KeyRound, ListOrdered, type LucideIcon } from 'lucide-react'
import type { SortOrder } from '@/lib/preferences'
import type { MenuItem } from '@/ui'

const SORT_LABEL: Record<SortOrder, string> = { relevance: 'Relevance', key_words: 'Key words', chronological: 'Text order' }
export const SORT_ICON: Record<SortOrder, LucideIcon> = { relevance: ArrowDownWideNarrow, key_words: KeyRound, chronological: ListOrdered }
const SORT_ORDERS: SortOrder[] = ['relevance', 'key_words', 'chronological']

export const sortLabel = (order: SortOrder): string => SORT_LABEL[order]

export const sortItems = (value: SortOrder, onChange: (order: SortOrder) => void): MenuItem[] =>
  SORT_ORDERS.map(order => ({ label: SORT_LABEL[order], selected: order === value, onSelect: () => onChange(order) }))
