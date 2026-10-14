import type { CollectionNode } from '@/api/types'

export type DropZone = 'before' | 'inside' | 'after'

const EDGE_SHARE = 0.25

export function zoneAt(offsetY: number, height: number, acceptsInside: boolean): DropZone {
  if (!acceptsInside) return offsetY < height / 2 ? 'before' : 'after'
  if (offsetY < height * EDGE_SHARE) return 'before'
  if (offsetY > height * (1 - EDGE_SHARE)) return 'after'
  return 'inside'
}

export function findNode(tree: CollectionNode[], id: number): CollectionNode | null {
  for (const node of tree) {
    if (node.id === id) return node
    const child = findNode(node.children, id)
    if (child) return child
  }
  return null
}

const siblingsOf = (tree: CollectionNode[], parentId: number | null): CollectionNode[] =>
  parentId === null ? tree : findNode(tree, parentId)?.children ?? []

/** Куда встанет перетаскиваемая коллекция; null — бросить нельзя: допустимых родителей перечисляет backend. */
export function collectionDrop(tree: CollectionNode[], draggedId: number, overId: number, zone: DropZone): { parentId: number | null; position: number } | null {
  const dragged = findNode(tree, draggedId)
  const over = findNode(tree, overId)
  if (!dragged || !over || dragged.id === over.id) return null
  const parentId = zone === 'inside' ? over.id : over.parent_id
  if (!dragged.move_targets.includes(parentId)) return null
  if (zone === 'inside') return { parentId, position: over.children.filter(c => c.id !== dragged.id).length }
  const siblings = siblingsOf(tree, parentId).filter(c => c.id !== dragged.id)
  const index = siblings.findIndex(c => c.id === over.id)
  return { parentId, position: zone === 'before' ? index : index + 1 }
}
