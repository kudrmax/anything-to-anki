import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CollectionNode, Scope, ScopeCounts, SourceStage, SourceSummary } from '@/api/types'
import { statsStore, useStats } from '@/hooks/useStats'
import { backTo } from '@/lib/backLink'
import { usePhone } from '@/lib/device'
import { OVERLAY } from '@/lib/hotkeys'
import { reviewPath, scopeQuery, sourceScope, useScope } from '@/lib/scope'
import { clickSelect, EMPTY_SELECTION, pruned, selectAll, type Selection } from '@/lib/selection'
import { findNode } from '@/lib/treeDrop'
import { typingIn } from '@/lib/typing'
import { Page } from '@/shell'
import { Banner, Button, Empty, Field, Stat, StatGrid, Toast, ToastStack, UndoToast, useToast, useUndo } from '@/ui'
import { AddSourceForm } from './AddSourceForm'
import { CollectionTree } from './CollectionTree'
import { MoveToModal } from './MoveToModal'
import { NameModal } from './NameModal'
import { RebuildDialog } from './RebuildDialog'
import { ScopeHeader } from './ScopeHeader'
import { ScopePicker } from './ScopePicker'
import { SelectionBar } from './SelectionBar'
import { SourceRow } from './SourceRow'
import { useCollections } from './useCollections'
import { useSourceBoard } from './useSourceBoard'
import css from './sources.module.css'

const STAGE_LABEL: Record<SourceStage, string> = {
  in_progress: 'In progress',
  preparing: 'Preparing',
  ready: 'Ready to review',
  reviewed: 'Reviewed',
}
const SCOPE_TITLE = { all: 'All sources', unsorted: 'Unsorted' } as const
const NO_COUNTS: ScopeCounts = { total: 0, reviewed: 0, pending: 0, progress: { decided: 0, total: 0 } }
const UNSORTED = 'Unsorted'
const EXPORT_PATH = '/export'
// Backend ставит коллекцию в конец, если позиция больше числа соседей.
const END_POSITION = Number.MAX_SAFE_INTEGER

type MoveTarget = { kind: 'sources'; ids: number[] } | { kind: 'collection'; id: number } | null
type Naming = { kind: 'rename'; node: CollectionNode } | { kind: 'create'; parent: CollectionNode } | null
type Operating = { id: number; title: string; operation: SourceSummary['available_operations'][number] } | null

const sourcesWord = (n: number) => (n === 1 ? '1 source' : `${n} sources`)

/** Путь к узлу для шапки: от корня к родителю. */
function ancestorsOf(collections: CollectionNode[], node: CollectionNode): CollectionNode[] {
  const parentOf = (child: CollectionNode) => child.parent_id === null ? null : findNode(collections, child.parent_id)
  const path: CollectionNode[] = []
  for (let parent = parentOf(node); parent; parent = parentOf(parent)) path.unshift(parent)
  return path
}

export function SourcesScreen() {
  const [scope, setScope] = useScope()
  const [query, setQuery] = useState('')
  const [selection, setSelection] = useState<Selection>(EMPTY_SELECTION)
  const [moveTarget, setMoveTarget] = useState<MoveTarget>(null)
  const [naming, setNaming] = useState<Naming>(null)
  const [operating, setOperating] = useState<Operating>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [processingAll, setProcessingAll] = useState(false)
  const [toast, showToast] = useToast()
  const undo = useUndo()
  const stats = useStats()
  const navigate = useNavigate()
  const isPhone = usePhone()
  const listLabel = useId()

  // Выбор и поиск принадлежат области: любая её смена (дерево, ссылка, «назад») их сбрасывает.
  const [shownScope, setShownScope] = useState<Scope>(scope)
  if (shownScope !== scope) {
    setShownScope(scope)
    setSelection(EMPTY_SELECTION)
    setQuery('')
  }

  const onError = useCallback((message: string) => showToast(message), [showToast])
  const boardReload = useRef<() => Promise<void>>(async () => {})
  const collections = useCollections({ onUndo: undo.show, onError, onSourcesMoved: () => void boardReload.current() })
  const board = useSourceBoard(scope, query, {
    onMissingScope: () => setScope('all', { replace: true }),
    onError,
    onChanged: () => void collections.reload(),
  })
  useLayoutEffect(() => {
    boardReload.current = board.reload
  })

  const tree = collections.tree
  const reloadBoard = useCallback(() => void boardReload.current(), [])
  const open = (next: Scope) => {
    setPickerOpen(false)
    setScope(next)
  }

  const order = useMemo(() => board.board?.groups.flatMap(g => g.sources.map(s => s.id)) ?? [], [board.board])
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

  const node = typeof scope === 'number' && tree ? findNode(tree.collections, scope) : null
  const ancestors = tree && node ? ancestorsOf(tree.collections, node) : []
  const counts = node?.counts ?? (tree ? (scope === 'unsorted' ? tree.unsorted : tree.all) : NO_COUNTS)
  const title = node?.name ?? board.board?.title ?? (typeof scope === 'number' ? '' : SCOPE_TITLE[scope])
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

  const review = (id: number) => navigate(reviewPath(sourceScope(id)), { state: backTo(`/${scopeQuery(scope)}`) })
  const exportSource = (id: number) => navigate(`/sources/${id}/export`)
  const exportScope = () => navigate(`${EXPORT_PATH}${scopeQuery(scope)}`)

  const processAll = async () => {
    setProcessingAll(true)
    try {
      await board.processPending()
    } finally {
      setProcessingAll(false)
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
    void collections.remove(id).then(deleted => { if (deleted && scope === id) setScope('all', { replace: true }) })
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
        <Stat value={stats?.learn_count ?? 0} label="to learn" />
        <Stat value={stats?.known_word_count ?? 0} label="known words" />
        <Stat value={stats?.candidate_count ?? 0} label="candidates" wide />
      </StatGrid>
      {tree && (
        <CollectionTree
          tree={tree}
          scope={scope}
          onSelect={open}
          onCreate={(name, parentId) => void collections.create(name, parentId)}
          onRename={(id, name) => void collections.rename(id, name)}
          onMove={(id, parentId, position) => void collections.move(id, parentId, position)}
          onDelete={deleteCollection}
          onMoveTo={id => setMoveTarget({ kind: 'collection', id })}
          onDropSources={placeSources}
          draggable={!isPhone}
        />
      )}
    </>
  )

  const banner = board.vpnBlocked && <Banner tone="warn">AI unavailable — turn on VPN</Banner>

  const groups = board.board?.groups.filter(g => g.sources.length > 0) ?? []
  const empty = (() => {
    if (!board.board || !tree || groups.length > 0) return null
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
      banner={banner}
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
            onExport={exportScope}
            onRename={() => node && setNaming({ kind: 'rename', node })}
            onNewSubcollection={() => node && setNaming({ kind: 'create', parent: node })}
            onMoveTo={() => node && setMoveTarget({ kind: 'collection', id: node.id })}
            onDelete={() => node && deleteCollection(node.id)}
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
          {groups.length > 0 && (
            <div role="listbox" aria-multiselectable="true" aria-labelledby={listLabel}>
              <span id={listLabel} hidden>{title}</span>
              {groups.map(group => {
                const headingId = `${listLabel}-${group.stage}`
                return (
                  <section key={group.stage} className={css.group} role="group" aria-labelledby={headingId}>
                    <h2 id={headingId} className={css.groupTitle}>{STAGE_LABEL[group.stage]}<span>{group.sources.length}</span></h2>
                    {group.sources.map((source, index) => (
                      <SourceRow
                        key={source.id}
                        source={source}
                        selected={visibleSelection.ids.has(source.id)}
                        showPath={scope === 'all' || (typeof scope === 'number' && source.collection_id !== scope)}
                        primary={group.stage === 'in_progress' && index === 0}
                        onProcess={id => void board.process(id)}
                        onGenerate={id => void board.generate(id)}
                        onCancelGeneration={id => void board.cancelGeneration(id)}
                        onRetryGeneration={id => void board.retryGeneration(id)}
                        onReview={review}
                        onExport={exportSource}
                        onDelete={deleteSource}
                        onRename={(id, newTitle) => void board.rename(id, newTitle)}
                        onOperation={(id, operation) => setOperating({ id, title: source.title, operation })}
                        onRowClick={rowClick}
                        onMoveTo={id => setMoveTarget({ kind: 'sources', ids: [id] })}
                        dragIds={() => dragIds(source.id)}
                        draggable={!isPhone}
                        onLongPress={longPress}
                      />
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
          sourceId={operating.id}
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
      <ToastStack raised={selectedIds.length > 0}>
        <Toast message={toast} tone="warn" />
        <UndoToast offer={undo.offer} onUndo={() => void undo.run()} />
      </ToastStack>
    </Page>
  )
}
