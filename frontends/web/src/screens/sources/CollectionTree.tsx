import { useCallback, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { ChevronDown, ChevronRight, Inbox, Layers, Plus, type LucideIcon } from 'lucide-react'
import type { CollectionNode, CollectionTree as Tree, Scope, ScopeCounts } from '@/api/types'
import { useCollapsed } from '@/hooks/useCollapsed'
import { collectionDrop, zoneAt, type DropZone } from '@/lib/treeDrop'
import { Field, Icon, IconButton, Menu } from '@/ui'
import { collectionMenuItems } from './collectionMenu'
import css from './CollectionTree.module.css'

export const SOURCES_MIME = 'application/x-anki-sources'
export const COLLECTION_MIME = 'application/x-anki-collection'

type Editing = { kind: 'create'; parentId: number | null } | { kind: 'rename'; id: number } | null
type Hover = { id: number | 'unsorted'; zone: DropZone } | null

interface CollectionTreeProps {
  tree: Tree
  scope: Scope
  onSelect: (scope: Scope) => void
  onCreate: (name: string, parentId: number | null) => void
  onRename: (id: number, name: string) => void
  onMove: (id: number, parentId: number | null, position: number) => void
  onDelete: (id: number) => void
  onMoveTo: (id: number) => void
  onDropSources: (sourceIds: number[], collectionId: number | null) => void
  /** На телефоне дерево без перетаскивания. */
  draggable: boolean
}

export function CollectionTree(props: CollectionTreeProps) {
  const { tree, scope, onSelect, draggable } = props
  const { isCollapsed, toggle } = useCollapsed()
  const [editing, setEditing] = useState<Editing>(null)
  const [draft, setDraft] = useState('')
  const [hover, setHover] = useState<Hover>(null)
  const [draggedId, setDraggedId] = useState<number | null>(null)
  // Enter и Escape размонтируют поле, а размонтирование даёт blur: без флага имя уйдёт дважды.
  const settled = useRef(false)

  // Флаг снимается при появлении поля, а не в startEditing: меню собирает обработчики во время рендера, а там ref трогать нельзя.
  const armEditor = useCallback((input: HTMLInputElement | null) => { if (input) settled.current = false }, [])
  const startEditing = (next: Editing, initial: string) => {
    setDraft(initial)
    setEditing(next)
  }
  const startCreate = (parentId: number | null) => startEditing({ kind: 'create', parentId }, '')
  const startRename = (node: CollectionNode) => startEditing({ kind: 'rename', id: node.id }, node.name)
  const finish = (commit: boolean) => {
    if (settled.current) return
    settled.current = true
    const name = draft.trim()
    if (commit && name && editing?.kind === 'create') props.onCreate(name, editing.parentId)
    if (commit && name && editing?.kind === 'rename') props.onRename(editing.id, name)
    setEditing(null)
  }
  const onEditKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter') finish(true)
    if (e.key === 'Escape') finish(false)
  }
  const editor = (
    <Field ref={armEditor} autoFocus value={draft} placeholder="Collection name" onChange={e => setDraft(e.target.value)} onKeyDown={onEditKey} onBlur={() => finish(true)} />
  )

  const sourcesIn = (e: DragEvent): number[] | null => {
    const raw = e.dataTransfer.getData(SOURCES_MIME)
    return raw ? (JSON.parse(raw) as number[]) : null
  }
  const carries = (e: DragEvent, mime: string) => e.dataTransfer.types.includes(mime)

  const overNode = (e: DragEvent, node: CollectionNode) => {
    if (carries(e, SOURCES_MIME)) { e.preventDefault(); setHover({ id: node.id, zone: 'inside' }); return }
    if (!carries(e, COLLECTION_MIME) || draggedId === null) return
    const box = e.currentTarget.getBoundingClientRect()
    const zone = zoneAt(e.clientY - box.top, box.height, node.accepts_collections)
    if (!collectionDrop(tree.collections, draggedId, node.id, zone)) { setHover(null); return }
    e.preventDefault()
    setHover({ id: node.id, zone })
  }

  const dropOnNode = (e: DragEvent, node: CollectionNode) => {
    e.preventDefault()
    const sources = sourcesIn(e)
    if (sources) props.onDropSources(sources, node.id)
    else if (draggedId !== null && hover?.id === node.id) {
      const target = collectionDrop(tree.collections, draggedId, node.id, hover.zone)
      if (target) props.onMove(draggedId, target.parentId, target.position)
    }
    setHover(null)
    setDraggedId(null)
  }

  const menuFor = (node: CollectionNode) => collectionMenuItems(node, {
    onRename: () => startRename(node),
    onNewSubcollection: () => startCreate(node.id),
    onMoveTo: () => props.onMoveTo(node.id),
    onDelete: () => props.onDelete(node.id),
  })

  const row = (node: CollectionNode, depth: 0 | 1) => {
    const selected = scope === node.id
    const zone = hover?.id === node.id ? hover.zone : null
    const classes = [css.row, depth === 1 && css.sub, selected && css.on, zone && css[zone]].filter(Boolean).join(' ')
    if (editing?.kind === 'rename' && editing.id === node.id) return <div key={node.id} className={classes}>{editor}</div>
    const collapsed = isCollapsed(node.id)
    return (
      <div key={node.id}>
        <div className={css.cell}>
          <Menu openOn="contextmenu" align="start" items={menuFor(node)} trigger={
            <div
              className={classes}
              role="treeitem"
              aria-selected={selected}
              tabIndex={0}
              draggable={draggable}
              onClick={() => onSelect(node.id)}
              onDoubleClick={() => startRename(node)}
              onKeyDown={e => { if (e.key === 'F2') startRename(node); if (e.key === 'Enter') onSelect(node.id) }}
              onDragStart={e => { e.dataTransfer.setData(COLLECTION_MIME, String(node.id)); setDraggedId(node.id) }}
              onDragEnd={() => { setDraggedId(null); setHover(null) }}
              onDragOver={e => overNode(e, node)}
              onDragLeave={() => setHover(null)}
              onDrop={e => dropOnNode(e, node)}
            >
              {node.children.length > 0
                ? <button type="button" className={css.twisty} aria-label={collapsed ? 'Expand' : 'Collapse'} onClick={e => { e.stopPropagation(); toggle(node.id) }}><Icon as={collapsed ? ChevronRight : ChevronDown} /></button>
                : <span className={css.twisty} />}
              <span className={css.name}>{node.name}</span>
              <span className={css.count}>{node.counts.total}</span>
            </div>
          } />
        </div>
        {!collapsed && node.children.map(child => row(child, 1))}
        {editing?.kind === 'create' && editing.parentId === node.id && <div className={`${css.row} ${css.sub}`}>{editor}</div>}
      </div>
    )
  }

  const fixed = (key: 'all' | 'unsorted', label: string, icon: LucideIcon, counts: ScopeCounts) => (
    <div
      className={[css.row, scope === key && css.on, key === 'unsorted' && hover?.id === 'unsorted' && css.inside].filter(Boolean).join(' ')}
      role="treeitem"
      aria-selected={scope === key}
      tabIndex={0}
      onClick={() => onSelect(key)}
      onKeyDown={e => { if (e.key === 'Enter') onSelect(key) }}
      onDragOver={key === 'unsorted' ? e => { if (carries(e, SOURCES_MIME)) { e.preventDefault(); setHover({ id: 'unsorted', zone: 'inside' }) } } : undefined}
      onDragLeave={() => setHover(null)}
      onDrop={key === 'unsorted' ? e => { e.preventDefault(); const s = sourcesIn(e); if (s) props.onDropSources(s, null); setHover(null) } : undefined}
    >
      <span className={css.twisty}><Icon as={icon} /></span>
      <span className={css.name}>{label}</span>
      <span className={css.count}>{counts.total}</span>
    </div>
  )

  return (
    <nav className={css.tree} role="tree" aria-label="Collections">
      {fixed('all', 'All', Layers, tree.all)}
      {fixed('unsorted', 'Unsorted', Inbox, tree.unsorted)}
      <div className={css.heading}>
        <span>Collections</span>
        <IconButton icon={Plus} label="New collection" onClick={() => startCreate(null)} />
      </div>
      {tree.collections.map(node => row(node, 0))}
      {editing?.kind === 'create' && editing.parentId === null && <div className={css.row}>{editor}</div>}
      {tree.collections.length === 0 && editing === null && <p className={css.empty}>Group sources into collections and subcollections</p>}
    </nav>
  )
}
