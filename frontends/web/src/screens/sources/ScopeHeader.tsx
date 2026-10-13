import { Fragment } from 'react'
import { ChevronRight, Ellipsis } from 'lucide-react'
import type { CollectionNode, ScopeCounts } from '@/api/types'
import { Button, Icon, IconButton, Menu } from '@/ui'
import { collectionMenuItems } from './collectionMenu'
import css from './sources.module.css'

interface ScopeHeaderProps {
  title: string
  /** Путь открытого узла; последний элемент — он сам. */
  path: string[]
  counts: ScopeCounts
  /** Открытая коллекция; у All и Unsorted меню нет. */
  node: CollectionNode | null
  processing: boolean
  onProcessAll: () => void
  onExport: () => void
  onRename: () => void
  onNewSubcollection: () => void
  onMoveTo: () => void
  onDelete: () => void
}

export function ScopeHeader({ title, path, counts, node, processing, onProcessAll, onExport, onRename, onNewSubcollection, onMoveTo, onDelete }: ScopeHeaderProps) {
  const crumbs = path.slice(0, -1)
  return (
    <header className={css.scopeHeader}>
      <div className={css.scopeLead}>
        {crumbs.length > 0 && (
          <nav className={css.crumbs} aria-label="Breadcrumbs">
            {crumbs.map((crumb, index) => (
              <Fragment key={index}>
                <span>{crumb}</span>
                <Icon as={ChevronRight} size="s" />
              </Fragment>
            ))}
          </nav>
        )}
        <h1 className={css.scopeTitle}>{title}</h1>
        {counts.total > 0 && <span className={css.scopeProgress}>{counts.reviewed} of {counts.total} reviewed</span>}
      </div>
      <div className={css.scopeActions}>
        {counts.pending > 0 && <Button busy={processing} onClick={onProcessAll}>Process all ({counts.pending})</Button>}
        <Button onClick={onExport}>Export</Button>
        {node && (
          <Menu
            trigger={<IconButton icon={Ellipsis} label="Collection actions" />}
            items={collectionMenuItems(node, { onRename, onNewSubcollection, onMoveTo, onDelete })}
          />
        )}
      </div>
    </header>
  )
}
