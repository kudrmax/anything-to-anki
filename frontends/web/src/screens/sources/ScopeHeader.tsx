import { Fragment, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronRight, Ellipsis } from 'lucide-react'
import type { CollectionNode, ScopeCounts, SetOperation } from '@/api/types'
import { Button, Icon, IconButton, Menu, Progress, type MenuItem } from '@/ui'
import { offersProcess } from './processOffer'
import { ReviewAction } from './ReviewAction'
import { collectionMenuItems, scopeMenuItems } from './scopeMenu'
import css from './sources.module.css'

interface ScopeHeaderProps {
  title: string
  /** Предки открытой коллекции от корня к родителю: путь в одну строку, каждый кликабелен. */
  ancestors: CollectionNode[]
  /** null, пока дерево не загружено: действия от выдуманных счётчиков не показываются. */
  counts: ScopeCounts | null
  /** Открытая коллекция; у All и Unsorted в меню только Export и операции. */
  node: CollectionNode | null
  processing: boolean
  onOpenAncestor: (id: number) => void
  onProcessAll: () => void
  /** Ревью открытой области как одного набора. */
  onReview: () => void
  onExport: () => void
  /** Rebuild или Refresh всей области. */
  onOperation: (operation: SetOperation) => void
  onRename: () => void
  onNewSubcollection: () => void
  onMoveTo: () => void
  onDelete: () => void
  /** Группировка и сортировка списка: в том же меню, отдельной группой. */
  viewItems: MenuItem[]
}

type Crumb = { key: string; content: ReactNode }

function crumbLinks(ancestors: CollectionNode[], onOpen: (id: number) => void): Crumb[] {
  return ancestors.map(ancestor => ({
    key: String(ancestor.id),
    content: <button type="button" className={css.scopeParent} title={ancestor.name} onClick={() => onOpen(ancestor.id)}>{ancestor.name}</button>,
  }))
}

/** Середина пути сворачивается в «…»: «первый › … › родитель › текущая». */
function foldMiddle(crumbs: Crumb[], ancestors: CollectionNode[]): Crumb[] {
  if (crumbs.length <= 2) return crumbs
  const hidden = ancestors.slice(1, -1).map(a => a.name).join(' › ')
  return [crumbs[0], { key: 'hidden', content: <span className={css.scopeGap} title={hidden}>…</span> }, crumbs[crumbs.length - 1]]
}

function CrumbTrail({ crumbs }: { crumbs: Crumb[] }) {
  return crumbs.map(crumb => (
    <Fragment key={crumb.key}>
      {crumb.content}
      <span className={css.scopeSep}><Icon as={ChevronRight} size="s" /></span>
    </Fragment>
  ))
}

/** Путь целиком, пока он влезает в строку; середина сворачивается, только когда места не хватает. */
function ScopeTitle({ title, ancestors, onOpen }: { title: string; ancestors: CollectionNode[]; onOpen: (id: number) => void }) {
  const lineRef = useRef<HTMLHeadingElement>(null)
  const fullRef = useRef<HTMLDivElement>(null)
  const [folded, setFolded] = useState(false)
  useLayoutEffect(() => {
    const line = lineRef.current
    const full = fullRef.current
    if (!line || !full) return
    const fit = () => setFolded(full.offsetWidth > line.clientWidth)
    fit()
    const observer = new ResizeObserver(fit)
    observer.observe(line)
    observer.observe(full)
    return () => observer.disconnect()
  }, [])
  const crumbs = crumbLinks(ancestors, onOpen)
  const name = <span className={css.scopeName} title={title}>{title}</span>
  return (
    <div className={css.scopeTitleLine}>
      <h1 ref={lineRef} className={css.scopeTitle}>
        <CrumbTrail crumbs={folded ? foldMiddle(crumbs, ancestors) : crumbs} />
        {name}
      </h1>
      <div className={css.scopeMeasureBox} aria-hidden inert>
        <div ref={fullRef} className={`${css.scopeTitle} ${css.scopeMeasure}`}>
          <CrumbTrail crumbs={crumbs} />
          {name}
        </div>
      </div>
    </div>
  )
}

/** Высота и места кнопок не зависят от области и глубины: при переключении ничего не прыгает. */
export function ScopeHeader({ title, ancestors, counts, node, processing, onOpenAncestor, onProcessAll, onReview, onExport, onOperation, onRename, onNewSubcollection, onMoveTo, onDelete, viewItems }: ScopeHeaderProps) {
  const menuItems: MenuItem[] = (() => {
    if (node) return collectionMenuItems(node, { onExport, onOperation, onRename, onNewSubcollection, onMoveTo, onDelete, viewItems })
    return counts ? scopeMenuItems(counts, { onExport, onOperation, viewItems }) : []
  })()
  return (
    <header className={css.scopeHeader}>
      <div className={css.scopeLead}>
        <ScopeTitle title={title} ancestors={ancestors} onOpen={onOpenAncestor} />
        <span className={css.scopeProgress}>
          {counts && (counts.total > 0
            ? <>
                <Progress inline value={counts.review_fraction} />
                {`${counts.reviewed} of ${counts.total} reviewed · ${counts.progress_caption}`}
              </>
            : 'No sources yet')}
        </span>
      </div>
      <div className={css.scopeActions}>
        {counts?.can_process && !offersProcess(counts.status) && <Button busy={processing} onClick={onProcessAll}>Process all ({counts.pending})</Button>}
        {counts && (
          <ReviewAction
            status={counts.status}
            canProcess={counts.can_process}
            canReview={counts.can_review}
            primary={false}
            busy={processing}
            onProcess={onProcessAll}
            onReview={onReview}
          />
        )}
        {menuItems.length > 0
          ? <Menu trigger={<IconButton icon={Ellipsis} label={node ? 'Collection actions' : 'Actions'} />} items={menuItems} />
          : <span className={css.scopeSlot} aria-hidden />}
      </div>
    </header>
  )
}
