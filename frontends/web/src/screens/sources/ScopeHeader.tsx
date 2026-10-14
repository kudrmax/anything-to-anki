import { ChevronRight, Ellipsis } from 'lucide-react'
import type { CollectionNode, ScopeCounts } from '@/api/types'
import { Button, Icon, IconButton, Menu } from '@/ui'
import { collectionMenuItems } from './collectionMenu'
import css from './sources.module.css'

interface ScopeHeaderProps {
  title: string
  /** Родитель открытой подколлекции: путь в одну строку, родитель кликабелен. */
  parent: CollectionNode | null
  counts: ScopeCounts
  /** Открытая коллекция; у All и Unsorted меню нет, но место под него держится. */
  node: CollectionNode | null
  processing: boolean
  onOpenParent: (id: number) => void
  onProcessAll: () => void
  onExport: () => void
  onRename: () => void
  onNewSubcollection: () => void
  onMoveTo: () => void
  onDelete: () => void
}

/** Высота и места кнопок не зависят от области: при переключении ничего не прыгает. */
export function ScopeHeader({ title, parent, counts, node, processing, onOpenParent, onProcessAll, onExport, onRename, onNewSubcollection, onMoveTo, onDelete }: ScopeHeaderProps) {
  return (
    <header className={css.scopeHeader}>
      <div className={css.scopeLead}>
        <h1 className={css.scopeTitle}>
          {parent && (
            <>
              <button type="button" className={css.scopeParent} onClick={() => onOpenParent(parent.id)}>{parent.name}</button>
              <span className={css.scopeSep}><Icon as={ChevronRight} size="s" /></span>
            </>
          )}
          <span className={css.scopeName}>{title}</span>
        </h1>
        <span className={css.scopeProgress}>
          {counts.total > 0 ? `${counts.reviewed} of ${counts.total} reviewed` : 'No sources yet'}
        </span>
      </div>
      <div className={css.scopeActions}>
        {counts.pending > 0 && <Button busy={processing} onClick={onProcessAll}>Process all ({counts.pending})</Button>}
        <Button onClick={onExport}>Export</Button>
        {node
          ? <Menu
              trigger={<IconButton icon={Ellipsis} label="Collection actions" />}
              items={collectionMenuItems(node, { onRename, onNewSubcollection, onMoveTo, onDelete })}
            />
          : <span className={css.scopeSlot} aria-hidden />}
      </div>
    </header>
  )
}
