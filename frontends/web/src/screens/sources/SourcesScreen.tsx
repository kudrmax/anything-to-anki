import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CollectionNode, RecentCollectionItem, Scope, SetOperation, SetScope, SourcesView, SourceStage, SourceSummary } from '@/api/types'
import { statsStore, useStats } from '@/hooks/useStats'
import { backTo } from '@/lib/backLink'
import { usePhone } from '@/lib/device'
import { OVERLAY } from '@/lib/hotkeys'
import { exportPath, reviewPath, sourceScope, useView, viewPath } from '@/lib/scope'
import { clickSelect, EMPTY_SELECTION, pruned, selectAll, type Selection } from '@/lib/selection'
import { findNode } from '@/lib/treeDrop'
import { typingIn } from '@/lib/typing'
import { Page } from '@/shell'
import { Button, Empty, Field, Stat, StatGrid, Toast, ToastStack, UndoToast, useToast, useUndo } from '@/ui'
import { AddSourceForm } from './AddSourceForm'
import { CollectionTree } from './CollectionTree'
import { MoveToModal } from './MoveToModal'
import { NameModal } from './NameModal'
import { RebuildDialog } from './RebuildDialog'
import { RecentCollectionRow } from './RecentCollectionRow'
import { ScopeHeader } from './ScopeHeader'
import { collectionMenuItems } from './scopeMenu'
import { ScopePicker } from './ScopePicker'
import { SelectionBar } from './SelectionBar'
import { sourceOrderItems } from './sourceOrderMenu'
import { SourceRow } from './SourceRow'
import { useCollections } from './useCollections'
import { useSourceBoard } from './useSourceBoard'
import { useSourceOrder } from './useSourceOrder'
import css from './sources.module.css'

const STAGE_LABEL: Record<SourceStage, string> = {
  in_progress: 'In progress',
  preparing: 'Preparing',
  ready: 'Ready to review',
  reviewed: 'Reviewed',
}
const VIEW_TITLE = { recent: 'Recent', all: 'All sources', unsorted: 'Unsorted' } as const
const UNSORTED = 'Unsorted'
// Backend ставит коллекцию в конец, если позиция больше числа соседей.
const END_POSITION = Number.MAX_SAFE_INTEGER

type MoveTarget = { kind: 'sources'; ids: number[] } | { kind: 'collection'; id: number } | null
type Naming = { kind: 'rename'; node: CollectionNode } | { kind: 'create'; parent: CollectionNode } | null
type Operating = { scope: SetScope; title: string; operation: SetOperation } | null

const sourcesWord = (n: number) => (n === 1 ? '1 source' : `${n} sources`)

/** Путь к узлу для шапки: от корня к родителю. */
function ancestorsOf(collections: CollectionNode[], node: CollectionNode): CollectionNode[] {
  const parentOf = (child: CollectionNode) => child.parent_id === null ? null : findNode(collections, child.parent_id)
  const path: CollectionNode[] = []
  for (let parent = parentOf(node); parent; parent = parentOf(parent)) path.unshift(parent)
  return path
}

export function SourcesScreen() {
  const [view, setView] = useView()
  // Recent — не область: у него нет ни ревью, ни экспорта, ни порядка целиком.
  const scope: Scope | null = view === 'recent' ? null : view
  const [query, setQuery] = useState('')
  const [selection, setSelection] = useState<Selection>(EMPTY_SELECTION)
  const [moveTarget, setMoveTarget] = useState<MoveTarget>(null)
  const [naming, setNaming] = useState<Naming>(null)
  const [operating, setOperating] = useState<Operating>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [processingAll, setProcessingAll] = useState(false)
  const [processingCollection, setProcessingCollection] = useState<number | null>(null)
  const [toast, showToast] = useToast()
  const undo = useUndo()
  const stats = useStats()
  const navigate = useNavigate()
  const isPhone = usePhone()
  const listLabel = useId()

  // Выбор и поиск принадлежат разделу: любая его смена (дерево, ссылка, «назад») их сбрасывает.
  const [shownView, setShownView] = useState<SourcesView>(view)
  if (shownView !== view) {
    setShownView(view)
    setSelection(EMPTY_SELECTION)
    setQuery('')
  }

  const onError = useCallback((message: string) => showToast(message), [showToast])
  const boardReload = useRef<() => Promise<void>>(async () => {})
  const collections = useCollections({ onUndo: undo.show, onError, onSourcesMoved: () => void boardReload.current() })
  const board = useSourceBoard(view, query, {
    onMissingScope: () => setView('recent', { replace: true }),
    onError,
    onChanged: () => void collections.reload(),
  })
  useLayoutEffect(() => {
    boardReload.current = board.reload
  })
  const sourceOrder = useSourceOrder({ onChanged: () => void boardReload.current(), onError })

  const tree = collections.tree
  const reloadBoard = useCallback(() => void boardReload.current(), [])
  const open = (next: SourcesView) => {
    setPickerOpen(false)
    setView(next)
  }

  const order = useMemo(() => {
    if (board.recent) return board.recent.items.flatMap(item => (item.kind === 'source' ? [item.source.id] : []))
    return board.board?.groups.flatMap(g => g.sources.map(s => s.id)) ?? []
  }, [board.board, board.recent])
  const visibleSelection = pruned(selection, order)
  const selectedIds = order.filter(id => visibleSelection.ids.has(id))

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (typingIn(event.target) || document.querySelector(OVERLAY)) return
      if (event.key.toLowerCase() === 'a' && (event.metaKey || event.ctrlKey) && !event.shiftKey && !event.altKey) {
        if (order.length === 0) return
        event.preventDefault()
        setSelection(selectAll(order))
      }
      if (event.key === 'Escape') setSelection(EMPTY_SELECTION)
    }
    // Захват: открытое окно или меню ещё в DOM, когда его собственный Esc только начинает его закрывать.
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [order])

  const added = async () => {
    await Promise.all([board.reload(), statsStore.refresh()])
  }
  const addForm = <AddSourceForm onReload={added} onToast={showToast} />

  const node = typeof view === 'number' && tree ? findNode(tree.collections, view) : null
  const ancestors = tree && node ? ancestorsOf(tree.collections, node) : []
  const counts = (() => {
    if (!tree || scope === null) return null
    if (typeof scope === 'number') return node?.counts ?? null
    return scope === 'unsorted' ? tree.unsorted : tree.all
  })()
  const title = node?.name ?? (typeof view === 'number' ? board.board?.title ?? '' : VIEW_TITLE[view])
  const nameOf = (collectionId: number | null) =>
    collectionId === null ? UNSORTED : (tree && findNode(tree.collections, collectionId)?.name) ?? ''

  const clearSelection = () => setSelection(EMPTY_SELECTION)
  const rowClick = (e: MouseEvent, id: number) => {
    const toggle = e.metaKey || e.ctrlKey
    if (!toggle && !e.shiftKey && visibleSelection.ids.size === 0) return false
    setSelection(clickSelect(visibleSelection, order, id, { toggle, range: e.shiftKey }))
    return true
  }
  const longPress = (id: number) => setSelection(clickSelect(visibleSelection, order, id, { toggle: true, range: false }))
  const dragIds = (id: number) => (visibleSelection.ids.has(id) ? selectedIds : [id])

  // Ревью и экспорт возвращают на открытый раздел.
  const backHere = backTo(viewPath(view))
  const review = (id: number) => navigate(reviewPath(sourceScope(id)), { state: backHere })
  const exportSet = (set: SetScope) => navigate(exportPath(set), { state: backHere })
  const operate = (set: SetScope, setTitle: string, operation: SetOperation) => setOperating({ scope: set, title: setTitle, operation })

  const processAll = async () => {
    if (scope === null) return
    setProcessingAll(true)
    try {
      await board.processPending(scope)
    } finally {
      setProcessingAll(false)
    }
  }
  const processCollection = async (id: number) => {
    setProcessingCollection(id)
    try {
      await board.processPending(id)
    } finally {
      setProcessingCollection(null)
    }
  }

  const deleteSource = (id: number) => {
    if (window.confirm('Delete this source and all its candidates?')) void board.remove(id)
  }
  const deleteSelected = () => {
    const ids = selectedIds
    const what = ids.length === 1 ? 'this source and all its candidates' : `${ids.length} sources and all their candidates`
    if (window.confirm(`Delete ${what}?`)) void board.deleteSelected(ids).then(clearSelection)
  }
  const processSelected = () => void board.processSelected(selectedIds).then(clearSelection)

  const deleteCollection = (id: number) => {
    void collections.remove(id).then(deleted => { if (deleted && view === id) setView('recent', { replace: true }) })
  }
  const placeSources = (ids: number[], collectionId: number | null) => {
    const moved = new Set(ids)
    void collections.place(ids, collectionId, nameOf(collectionId)).then(placed => {
      if (!placed) return
      // Перенесли одну невыбранную строку — чужой выбор остаётся.
      setSelection(current => {
        const { ids: shown } = pruned(current, order)
        return shown.size === moved.size && [...shown].every(id => moved.has(id)) ? EMPTY_SELECTION : current
      })
    })
  }
  const pickMoveTarget = (collectionId: number | null) => {
    if (moveTarget?.kind === 'sources') placeSources(moveTarget.ids, collectionId)
    if (moveTarget?.kind === 'collection') void collections.move(moveTarget.id, collectionId, END_POSITION)
    setMoveTarget(null)
  }
  const submitName = (name: string) => {
    if (naming?.kind === 'rename') void collections.rename(naming.node.id, name)
    if (naming?.kind === 'create') void collections.create(name, naming.parent.id)
    setNaming(null)
  }

  const side = (
    <>
      {!isPhone && addForm}
      <StatGrid>
        <Stat value={stats?.export_pending_count ?? 0} label="to learn" />
        <Stat value={stats?.learning_count ?? 0} label="learning" />
        <Stat value={stats?.known_word_count ?? 0} label="known words" />
        <Stat value={stats?.candidate_count ?? 0} label="candidates" />
      </StatGrid>
      {tree && (
        <CollectionTree
          tree={tree}
          scope={view}
          onSelect={open}
          onCreate={(name, parentId) => void collections.create(name, parentId)}
          onRename={(id, name) => void collections.rename(id, name)}
          onMove={(id, parentId, position) => void collections.move(id, parentId, position)}
          onDelete={deleteCollection}
          onMoveTo={id => setMoveTarget({ kind: 'collection', id })}
          onFavorite={(id, favorite) => void collections.setFavorite(id, favorite)}
          onExport={exportSet}
          onOperation={(id, operation) => operate(id, findNode(tree.collections, id)?.name ?? '', operation)}
          onDropSources={placeSources}
          draggable={!isPhone}
        />
      )}
    </>
  )

  const groups = board.board?.groups.filter(g => g.sources.length > 0) ?? []
  const recentItems = board.recent?.items ?? []
  const empty = (() => {
    if ((!board.board && !board.recent) || !tree || groups.length > 0 || recentItems.length > 0) return null
    if (query.trim()) return <Empty flush>Nothing matches “{query.trim()}”</Empty>
    if (node) {
      // Внутри пустой коллекции перетаскивать нечего: источники берут в другом разделе.
      const from: Scope = tree.unsorted.total > 0 ? 'unsorted' : 'all'
      return (
        <Empty flush>
          <div className={css.emptyStart}>
            <span>{node.name} is empty. {isPhone ? 'Open a source’s menu and choose Move to…' : 'Drag sources onto it in the tree, or choose Move to… in a source’s menu.'}</span>
            <Button onClick={() => open(from)}>{from === 'unsorted' ? 'Open Unsorted' : 'Open all sources'}</Button>
          </div>
        </Empty>
      )
    }
    if (board.recent && tree.all.total > 0) return <Empty flush>Sources and collections you add or review show up here</Empty>
    if (tree.all.total === 0) {
      return (
        <Empty flush>
          <div className={css.emptyStart}>
            <span>No sources yet. Add a text, a video, a book or a topic to start.</span>
          </div>
        </Empty>
      )
    }
    return <Empty flush>{scope === 'unsorted' ? 'Every source is in a collection' : 'No sources here'}</Empty>
  })()

  const sourceRow = (source: SourceSummary, showPath: boolean, primary: boolean) => (
    <SourceRow
      key={source.id}
      source={source}
      selected={visibleSelection.ids.has(source.id)}
      showPath={showPath}
      primary={primary}
      onProcess={id => void board.process(id)}
      onGenerate={id => void board.generate(id)}
      onCancelGeneration={id => void board.cancelGeneration(id)}
      onRetryGeneration={id => void board.retryGeneration(id)}
      onReview={review}
      onExport={id => exportSet(sourceScope(id))}
      onDelete={deleteSource}
      onRename={(id, newTitle) => void board.rename(id, newTitle)}
      onOperation={(id, operation) => operate(sourceScope(id), source.title, operation)}
      onRowClick={rowClick}
      onMoveTo={id => setMoveTarget({ kind: 'sources', ids: [id] })}
      dragIds={() => dragIds(source.id)}
      draggable={!isPhone}
      onLongPress={longPress}
    />
  )

  const recentCollectionRow = (item: RecentCollectionItem) => {
    // Дерево перечитывается после любой правки коллекций, поэтому имя, счётчики и путь берутся из него.
    const fresh = tree ? findNode(tree.collections, item.collection.id) : item.collection
    if (!fresh) return null
    const path = tree ? ancestorsOf(tree.collections, fresh).map(a => a.name) : item.path
    const menuItems = collectionMenuItems(fresh, {
      onExport: () => exportSet(fresh.id),
      onOperation: operation => operate(fresh.id, fresh.name, operation),
      onRename: () => setNaming({ kind: 'rename', node: fresh }),
      onNewSubcollection: () => setNaming({ kind: 'create', parent: fresh }),
      onMoveTo: () => setMoveTarget({ kind: 'collection', id: fresh.id }),
      onFavorite: () => void collections.setFavorite(fresh.id, !fresh.favorite),
      onDelete: () => deleteCollection(fresh.id),
    })
    return (
      <RecentCollectionRow
        key={`collection-${fresh.id}`}
        node={fresh}
        path={path}
        processing={processingCollection === fresh.id}
        menuItems={menuItems}
        onProcess={() => void processCollection(fresh.id)}
        onReview={() => navigate(reviewPath(fresh.id), { state: backHere })}
      />
    )
  }

  const movingCollection = moveTarget?.kind === 'collection' && tree ? findNode(tree.collections, moveTarget.id) : null

  return (
    <Page
      wide
      fill
      header={
        <ScopePicker title={title} open={pickerOpen} onOpen={() => setPickerOpen(true)} onClose={() => setPickerOpen(false)}>
          {side}
        </ScopePicker>
      }
    >
      <div className={css.layout}>
        {!isPhone && <aside className={css.side} aria-label="Collections">{side}</aside>}
        <div className={css.main}>
          {isPhone && <div className={css.phoneAdd}>{addForm}</div>}
          <ScopeHeader
            title={title}
            ancestors={ancestors}
            onOpenAncestor={open}
            counts={counts}
            node={node}
            processing={processingAll}
            onProcessAll={() => void processAll()}
            onReview={() => { if (scope !== null) navigate(reviewPath(scope), { state: backHere }) }}
            onExport={() => { if (scope !== null) exportSet(scope) }}
            onOperation={operation => { if (scope !== null) operate(scope, title, operation) }}
            onRename={() => node && setNaming({ kind: 'rename', node })}
            onNewSubcollection={() => node && setNaming({ kind: 'create', parent: node })}
            onMoveTo={() => node && setMoveTarget({ kind: 'collection', id: node.id })}
            onFavorite={() => node && void collections.setFavorite(node.id, !node.favorite)}
            onDelete={() => node && deleteCollection(node.id)}
            viewItems={sourceOrder.order && view !== 'recent'
              ? sourceOrderItems(sourceOrder.order, {
                onGrouping: grouping => void sourceOrder.setGrouping(grouping),
                onSort: sort => void sourceOrder.setSort(sort),
                onDirection: direction => void sourceOrder.setDirection(direction),
              })
              : []}
          />
          <Field
            className={css.search}
            type="search"
            aria-label="Search sources"
            placeholder={`Search in ${title}`}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Escape') setQuery('') }}
          />
          <div className={board.stale ? `${css.listArea} ${css.stale}` : css.listArea} aria-busy={board.stale}>
          {empty}
          {recentItems.length > 0 && (
            <div role="listbox" aria-multiselectable="true" aria-labelledby={listLabel}>
              <span id={listLabel} hidden>{title}</span>
              <section className={css.group} role="group" aria-labelledby={listLabel}>
                {recentItems.map(item => (item.kind === 'source' ? sourceRow(item.source, true, false) : recentCollectionRow(item)))}
              </section>
            </div>
          )}
          {groups.length > 0 && (
            <div role="listbox" aria-multiselectable="true" aria-labelledby={listLabel}>
              <span id={listLabel} hidden>{title}</span>
              {groups.map(group => {
                const headingId = `${listLabel}-${group.stage ?? 'all'}`
                return (
                  <section key={group.stage ?? 'all'} className={css.group} role="group" aria-labelledby={group.stage ? headingId : listLabel}>
                    {group.stage && <h2 id={headingId} className={css.groupTitle}>{STAGE_LABEL[group.stage]}<span>{group.sources.length}</span></h2>}
                    {group.sources.map((source, index) => sourceRow(
                      source,
                      scope === 'all' || (typeof scope === 'number' && source.collection_id !== scope),
                      group.stage === 'in_progress' && index === 0,
                    ))}
                  </section>
                )
              })}
            </div>
          )}
          </div>
          {selectedIds.length > 0 && (
            <SelectionBar
              count={selectedIds.length}
              onMoveTo={() => setMoveTarget({ kind: 'sources', ids: selectedIds })}
              onProcess={processSelected}
              onDelete={deleteSelected}
              onClear={clearSelection}
            />
          )}
        </div>
      </div>
      {operating && (
        <RebuildDialog
          scope={operating.scope}
          title={operating.title}
          operation={operating.operation}
          onFinished={reloadBoard}
          onClose={() => { setOperating(null); void board.reload() }}
        />
      )}
      {moveTarget && tree && (
        <MoveToModal
          tree={tree}
          title={moveTarget.kind === 'sources' ? `Move ${sourcesWord(moveTarget.ids.length)} to…` : `Move ${movingCollection?.name ?? 'collection'} to…`}
          excludeId={moveTarget.kind === 'collection' ? moveTarget.id : undefined}
          collectionsOnly={moveTarget.kind === 'collection'}
          onPick={pickMoveTarget}
          onClose={() => setMoveTarget(null)}
        />
      )}
      {naming && (
        <NameModal
          title={naming.kind === 'rename' ? 'Rename collection' : `New subcollection in ${naming.parent.name}`}
          initial={naming.kind === 'rename' ? naming.node.name : ''}
          submitLabel={naming.kind === 'rename' ? 'Rename' : 'Create'}
          onSubmit={submitName}
          onClose={() => setNaming(null)}
        />
      )}
      <ToastStack above={selectedIds.length > 0 ? 'selection' : null}>
        <Toast message={toast} tone="warn" />
        <UndoToast offer={undo.offer} onUndo={() => void undo.run()} />
      </ToastStack>
    </Page>
  )
}
