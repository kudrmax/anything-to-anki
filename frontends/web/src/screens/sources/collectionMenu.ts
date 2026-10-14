import { FolderInput, FolderPlus, Pencil, Trash2 } from 'lucide-react'
import type { CollectionNode } from '@/api/types'
import type { MenuItem } from '@/ui'

export interface CollectionMenuHandlers {
  onRename: () => void
  onNewSubcollection: () => void
  onMoveTo: () => void
  onDelete: () => void
}

/** Одно меню коллекции и в дереве, и в шапке области. */
export function collectionMenuItems(node: CollectionNode, handlers: CollectionMenuHandlers): MenuItem[] {
  return [
    { label: 'Rename', icon: Pencil, onSelect: handlers.onRename },
    ...(node.accepts_collections ? [{ label: 'New subcollection', icon: FolderPlus, onSelect: handlers.onNewSubcollection }] : []),
    { label: 'Move to…', icon: FolderInput, onSelect: handlers.onMoveTo },
    { label: 'Delete', icon: Trash2, danger: true, separated: true, onSelect: handlers.onDelete },
  ]
}
