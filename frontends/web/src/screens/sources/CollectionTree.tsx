import { useCallback, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { ChevronDown, ChevronRight, Ellipsis, Folder, FolderOpen, FolderPlus, Inbox, Layers, Plus, Star, type LucideIcon } from 'lucide-react'
import type { CollectionNode, CollectionTree as Tree, Scope, ScopeCounts, SetOperation } from '@/api/types'
import { useCollapsed } from '@/hooks/useCollapsed'
import { TOOLTIP_LINE } from '@/lib/text/format'
import { collectionDrop, findNode, zoneAt, type DropZone } from '@/lib/treeDrop'
import { Icon, IconButton, Menu, Progress } from '@/ui'
import { collectionMenuItems } from './scopeMenu'
import css from './CollectionTree.module.css'

export const SOURCES_MIME = 'application/x-anki-sources'
export const COLLECTION_MIME = 'application/x-anki-collection'

/** Прогресс решений по всем источникам области и число источников; без кандидатов — только число. */
function Stats({ counts }: { counts: ScopeCounts }) {
  const { total, progress: { decided, total: candidates } } = counts
  const sources = `${total} ${total === 1 ? 'source' : 'sources'}`
  return (
    <span className={css.stats} title={candidates > 0 ? `${decided} of ${candidates} decided${TOOLTIP_LINE}${sources}` : sources}>
      {candidates > 0 && <>
        <Progress inline value={decided / candidates} />
        <span className={css.percent}>{Math.round((decided / candidates) * 100)}%</span>
      </>}
      <span className={css.count}>{total}</span>
    </span>
  )
}

type Editing = { kind: 'create'; parentId: number | null } | { kind: 'rename'; id: number } | null
type Hover = { id: number | 'unsorted' | `favorite-${number}`; zone: DropZone } | null

interface CollectionTreeProps {
  tree: Tree
  scope: Scope
  onSelect: (scope: Scope) => void
  onCreate: (name: string, parentId: number | null) => void
  onRename: (id: number, name: string) => void
  onMove: (id: number, parentId: number | null, position: number) => void
  onDelete: (id: number) => void
  onMoveTo: (id: number) => void
  onFavorite: (id: number, favorite: boolean) => void
  onExport: (id: number) => void
  /** Rebuild или Refresh коллекции целиком. */
  onOperation: (id: number, operation: SetOperation) => void
  onDropSources: (sourceIds: number[], collectionId: number | null) => void
  /** На телефоне дерево без перетаскивания. */
  draggable: boolean
}

export function CollectionTree(props: CollectionTreeProps) {
  const { tree, scope, onSelect, draggable } = props
  const { isCollapsed, toggle, expand } = useCollapsed()
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
  const startCreate = (parentId: number | null) => {
    if (parentId !== null) expand(parentId)
    startEditing({ kind: 'create', parentId }, '')
  }
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
  /** Поле встаёт на место имени: иконка и отступ остаются, строка не прыгает. */
  const editorRow = (count?: number) => (
    <div className={`${css.row} ${css.editing}`}>
      <span className={css.icon}><Icon as={Folder} size="s" /></span>
      <input
        ref={armEditor}
        autoFocus
        className={css.input}
        value={draft}
        placeholder="Collection name"
        aria-label="Collection name"
        onChange={e => setDraft(e.target.value)}
        onKeyDown={onEditKey}
        onBlur={() => finish(true)}
        onFocus={e => e.currentTarget.select()}
      />
      <span className={css.count}>{count}</span>
    </div>
  )

  const sourcesIn = (e: DragEvent): number[] | null => {
    const raw = e.dataTransfer.getData(SOURCES_MIME)
    return raw ? (JSON.parse(raw) as number[]) : null
  }
  const carries = (e: DragEvent, mime: string) => e.dataTransfer.types.includes(mime)

  /** Зона считается по самому событию: состояние hover могло не успеть обновиться. Середина строки — «внутрь», только если туда можно. */
  const zoneOf = (e: DragEvent, node: CollectionNode, draggedId: number): DropZone => {
    const box = e.currentTarget.getBoundingClientRect()
    const nestable = collectionDrop(tree.collections, draggedId, node.id, 'inside') !== null
    return zoneAt(e.clientY - box.top, box.height, nestable)
  }
  // Переход курсора на дочерний элемент строки — не уход со строки.
  const leave = (e: DragEvent) => {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return
    setHover(null)
  }

  const overNode = (e: DragEvent, node: CollectionNode) => {
    if (carries(e, SOURCES_MIME)) { e.preventDefault(); setHover({ id: node.id, zone: 'inside' }); return }
    if (!carries(e, COLLECTION_MIME) || draggedId === null) return
    const zone = zoneOf(e, node, draggedId)
    if (!collectionDrop(tree.collections, draggedId, node.id, zone)) { setHover(null); return }
    e.preventDefault()
    setHover({ id: node.id, zone })
  }

  const dropOnNode = (e: DragEvent, node: CollectionNode) => {
    e.preventDefault()
    const sources = sourcesIn(e)
    if (sources) props.onDropSources(sources, node.id)
    else if (draggedId !== null) {
      const target = collectionDrop(tree.collections, draggedId, node.id, zoneOf(e, node, draggedId))
      if (target) props.onMove(draggedId, target.parentId, target.position)
    }
    setHover(null)
    setDraggedId(null)
  }

  const menuFor = (node: CollectionNode) => collectionMenuItems(node, {
    onExport: () => props.onExport(node.id),
    onOperation: operation => props.onOperation(node.id, operation),
    onRename: () => startRename(node),
    onNewSubcollection: () => startCreate(node.id),
    onMoveTo: () => props.onMoveTo(node.id),
    onFavorite: () => props.onFavorite(node.id, !node.favorite),
    onDelete: () => props.onDelete(node.id),
  })

  const row = (node: CollectionNode) => {
    const selected = scope === node.id
    const zone = hover?.id === node.id ? hover.zone : null
    const classes = [css.row, selected && css.on, zone && css[zone]].filter(Boolean).join(' ')
    const collapsed = isCollapsed(node.id)
    const renaming = editing?.kind === 'rename' && editing.id === node.id
    const hasChildren = node.children.length > 0
    const creatingInside = editing?.kind === 'create' && editing.parentId === node.id
    const stop = (e: { stopPropagation: () => void }) => e.stopPropagation()
    return (
      <div key={node.id} className={css.item}>
        {renaming ? editorRow(node.counts.total) : <div className={css.cell}>
          <Menu openOn="contextmenu" align="start" items={menuFor(node)} trigger={
            <div
              className={classes}
              role="treeitem"
              aria-selected={selected}
              aria-expanded={hasChildren ? !collapsed : undefined}
              aria-level={node.depth}
              tabIndex={0}
              draggable={draggable}
              onClick={() => onSelect(node.id)}
              onDoubleClick={() => startRename(node)}
              onKeyDown={e => { if (e.key === 'F2') startRename(node); if (e.key === 'Enter') onSelect(node.id) }}
              onDragStart={e => { e.dataTransfer.setData(COLLECTION_MIME, String(node.id)); setDraggedId(node.id) }}
              onDragEnd={() => { setDraggedId(null); setHover(null) }}
              onDragOver={e => overNode(e, node)}
              onDragLeave={leave}
              onDrop={e => dropOnNode(e, node)}
            >
              {hasChildren
                ? <button
                    type="button"
                    className={[css.icon, css.twisty, collapsed && css.closed].filter(Boolean).join(' ')}
                    aria-label={collapsed ? 'Expand' : 'Collapse'}
                    onClick={e => { e.stopPropagation(); toggle(node.id) }}
                    onDoubleClick={stop}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') e.stopPropagation() }}
                  >
                    <span className={css.folder}><Icon as={selected ? FolderOpen : Folder} size="s" /></span>
                    <span className={css.chevron}><Icon as={collapsed ? ChevronRight : ChevronDown} size="s" /></span>
                  </button>
                : <span className={css.icon}><Icon as={selected ? FolderOpen : Folder} size="s" /></span>}
              <span className={css.name} title={node.name}>{node.name}</span>
              <span className={css.trail} onClick={stop} onDoubleClick={stop}>
                <Stats counts={node.counts} />
                <span className={css.actions}>
                  {node.accepts_collections && (
                    <button type="button" className={css.action} title="New subcollection" aria-label="New subcollection" onClick={() => startCreate(node.id)}>
                      <Icon as={FolderPlus} size="s" />
                    </button>
                  )}
                  <Menu align="start" items={menuFor(node)} trigger={
                    <button type="button" className={css.action} title="More" aria-label={`More for ${node.name}`}><Icon as={Ellipsis} size="s" /></button>
                  } />
                </span>
              </span>
            </div>
          } />
        </div>}
        {((hasChildren && !collapsed) || creatingInside) && (
          <div className={css.children} role="group">
            {!collapsed && node.children.map(row)}
            {creatingInside && <div className={css.item}>{editorRow()}</div>}
          </div>
        )}
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
      onDragLeave={leave}
      onDrop={key === 'unsorted' ? e => { e.preventDefault(); const s = sourcesIn(e); if (s) props.onDropSources(s, null); setHover(null) } : undefined}
    >
      <span className={css.icon}><Icon as={icon} size="s" /></span>
      <span className={css.name}>{label}</span>
      <span className={css.trail}><Stats counts={counts} /></span>
    </div>
  )

  /** Ярлык коллекции: открывает её и принимает источники, но не перетаскивается и не вкладывается. */
  const favorite = (node: CollectionNode) => {
    const key = `favorite-${node.id}` as const
    const selected = scope === node.id
    return (
      <div key={key} className={css.cell}>
        <Menu openOn="contextmenu" align="start" items={menuFor(node)} trigger={
          <div
            className={[css.row, selected && css.on, hover?.id === key && css.inside].filter(Boolean).join(' ')}
            role="treeitem"
            aria-selected={selected}
            tabIndex={0}
            onClick={() => onSelect(node.id)}
            onKeyDown={e => { if (e.key === 'Enter') onSelect(node.id) }}
            onDragOver={e => { if (carries(e, SOURCES_MIME)) { e.preventDefault(); setHover({ id: key, zone: 'inside' }) } }}
            onDragLeave={leave}
            onDrop={e => { e.preventDefault(); const s = sourcesIn(e); if (s) props.onDropSources(s, node.id); setHover(null) }}
          >
            <span className={css.icon}><Icon as={Star} size="s" /></span>
            <span className={css.name} title={node.name}>{node.name}</span>
            <span className={css.trail} onClick={e => e.stopPropagation()}>
              <Stats counts={node.counts} />
              <span className={css.actions}>
                <Menu align="start" items={menuFor(node)} trigger={
                  <button type="button" className={css.action} title="More" aria-label={`More for ${node.name}`}><Icon as={Ellipsis} size="s" /></button>
                } />
              </span>
            </span>
          </div>
        } />
      </div>
    )
  }
  const favorites = tree.favorites.flatMap(id => findNode(tree.collections, id) ?? [])

  return (
    <nav className={css.tree} role="tree" aria-label="Collections">
      {fixed('all', 'All', Layers, tree.all)}
      {fixed('unsorted', 'Unsorted', Inbox, tree.unsorted)}
      {favorites.length > 0 && <>
        <div className={css.heading}><span>Favorites</span></div>
        {favorites.map(favorite)}
      </>}
      <div className={css.heading}>
        <span>Collections</span>
        <IconButton icon={Plus} label="New collection" onClick={() => startCreate(null)} />
      </div>
      {tree.collections.map(row)}
      {editing?.kind === 'create' && editing.parentId === null && editorRow()}
      {tree.collections.length === 0 && editing === null && <p className={css.empty}>Group sources into collections and subcollections</p>}
    </nav>
  )
}
