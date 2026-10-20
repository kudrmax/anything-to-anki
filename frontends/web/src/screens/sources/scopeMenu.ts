import { FolderInput, FolderPlus, Pencil, RefreshCw, Trash2, Upload } from 'lucide-react'
import type { CollectionNode, SetOffer, SetOperation } from '@/api/types'
import type { MenuItem } from '@/ui'

/** Пункт есть, только если передан его обработчик; Export и операции решает backend. */
export interface ScopeMenuHandlers {
  onExport: () => void
  onOperation: (operation: SetOperation) => void
  onRename?: () => void
  onNewSubcollection?: () => void
  onMoveTo?: () => void
  onDelete?: () => void
  /** Вид списка (группировка, сортировка): отдельной группой перед Delete. */
  viewItems?: MenuItem[]
}

const OPERATION_LABEL: Record<SetOperation, string> = {
  update: 'Find words again…',
  recut: 'Process again…',
  refresh: 'Refresh…',
}

/** Одно меню «…» для источника и набора: в строке источника, в шапке области и в дереве. */
export function scopeMenuItems(offer: SetOffer, handlers: ScopeMenuHandlers): MenuItem[] {
  const { onExport, onOperation, onRename, onNewSubcollection, onMoveTo, onDelete, viewItems = [] } = handlers
  return [
    ...(offer.can_export ? [{ label: 'Export', icon: Upload, onSelect: onExport }] : []),
    ...(onRename ? [{ label: 'Rename', icon: Pencil, onSelect: onRename }] : []),
    ...(onNewSubcollection ? [{ label: 'New subcollection', icon: FolderPlus, onSelect: onNewSubcollection }] : []),
    ...(onMoveTo ? [{ label: 'Move to…', icon: FolderInput, onSelect: onMoveTo }] : []),
    ...offer.available_operations.map(operation => ({
      label: OPERATION_LABEL[operation],
      icon: RefreshCw,
      disabled: !offer.can_start_operation,
      hint: offer.operation_hint ?? undefined,
      onSelect: () => onOperation(operation),
    })),
    ...viewItems.map((item, index) => (index === 0 ? { ...item, separated: true } : item)),
    ...(onDelete ? [{ label: 'Delete', icon: Trash2, danger: true, separated: true, onSelect: onDelete }] : []),
  ]
}

/** Меню коллекции одно и в дереве, и в шапке: подколлекция — только там, где она поместится. */
export function collectionMenuItems(node: CollectionNode, handlers: Required<Omit<ScopeMenuHandlers, 'viewItems'>> & Pick<ScopeMenuHandlers, 'viewItems'>): MenuItem[] {
  return scopeMenuItems(node.counts, {
    ...handlers,
    onNewSubcollection: node.accepts_collections ? handlers.onNewSubcollection : undefined,
  })
}
