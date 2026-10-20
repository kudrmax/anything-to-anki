import { Fragment, type ReactNode } from 'react'
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
}

/** Длиннее этого путь сворачивает середину: «первый › … › родитель › текущая». */
const MAX_SHOWN_ANCESTORS = 2

function Crumbs({ ancestors, onOpen }: { ancestors: CollectionNode[]; onOpen: (id: number) => void }) {
  const link = (ancestor: CollectionNode) =>
    <button type="button" className={css.scopeParent} title={ancestor.name} onClick={() => onOpen(ancestor.id)}>{ancestor.name}</button>
  const hidden = ancestors.slice(1, -1)
  const crumbs: { key: string; content: ReactNode }[] = ancestors.length > MAX_SHOWN_ANCESTORS
    ? [
        { key: String(ancestors[0].id), content: link(ancestors[0]) },
        { key: 'hidden', content: <span className={css.scopeGap} title={hidden.map(a => a.name).join(' › ')}>…</span> },
        { key: String(ancestors[ancestors.length - 1].id), content: link(ancestors[ancestors.length - 1]) },
      ]
    : ancestors.map(ancestor => ({ key: String(ancestor.id), content: link(ancestor) }))
  return crumbs.map(crumb => (
    <Fragment key={crumb.key}>
      {crumb.content}
      <span className={css.scopeSep}><Icon as={ChevronRight} size="s" /></span>
    </Fragment>
  ))
}

/** Высота и места кнопок не зависят от области и глубины: при переключении ничего не прыгает. */
export function ScopeHeader({ title, ancestors, counts, node, processing, onOpenAncestor, onProcessAll, onReview, onExport, onOperation, onRename, onNewSubcollection, onMoveTo, onDelete }: ScopeHeaderProps) {
  const menuItems: MenuItem[] = (() => {
    if (node) return collectionMenuItems(node, { onExport, onOperation, onRename, onNewSubcollection, onMoveTo, onDelete })
    return counts ? scopeMenuItems(counts, { onExport, onOperation }) : []
  })()
  return (
    <header className={css.scopeHeader}>
      <div className={css.scopeLead}>
        <h1 className={css.scopeTitle}>
          <Crumbs ancestors={ancestors} onOpen={onOpenAncestor} />
          <span className={css.scopeName} title={title}>{title}</span>
        </h1>
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
