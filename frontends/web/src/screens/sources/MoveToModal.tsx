import { useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { Folder, FolderTree, Inbox, type LucideIcon } from 'lucide-react'
import type { CollectionNode, CollectionTree } from '@/api/types'
import { findNode } from '@/lib/treeDrop'
import { Button, Field, Icon, Modal } from '@/ui'
import css from './sources.module.css'

interface MoveToModalProps {
  tree: CollectionTree
  title: string
  /** Переносимая коллекция: её поддерева нет среди целей. */
  excludeId?: number
  /** Переносим коллекцию: цели — верхний уровень и коллекции, доступны только её move_targets. */
  collectionsOnly?: boolean
  onPick: (collectionId: number | null, name: string) => void
  onClose: () => void
}

interface Target {
  id: number | null
  name: string
  /** Путь к цели при поиске, когда отступов нет. */
  path: string[]
  /** Уровень отступа в списке: Unsorted, Top level и верхний уровень — 0. */
  indent: number
  icon: LucideIcon
  disabled: boolean
  current: boolean
}

const TOP_LEVEL = 'Top level'
const UNSORTED = 'Unsorted'

/** Все коллекции в порядке дерева, без поддерева исключённой. */
function flatten(nodes: CollectionNode[], excludeId: number | undefined, path: string[] = []): { node: CollectionNode; path: string[] }[] {
  return nodes
    .filter(node => node.id !== excludeId)
    .flatMap(node => [{ node, path }, ...flatten(node.children, excludeId, [...path, node.name])])
}

function targetsOf(tree: CollectionTree, excludeId: number | undefined, collectionsOnly: boolean): Target[] {
  const collections = flatten(tree.collections, excludeId)
  if (collectionsOnly) {
    const moving = excludeId === undefined ? null : findNode(tree.collections, excludeId)
    const allowed = (id: number | null) => moving?.move_targets.includes(id) ?? true
    const current = (id: number | null) => moving !== null && moving.parent_id === id
    return [
      { id: null, name: TOP_LEVEL, path: [], indent: 0, icon: FolderTree, disabled: !allowed(null), current: current(null) },
      ...collections.map(({ node, path }) => ({
        id: node.id, name: node.name, path, indent: node.depth - 1, icon: Folder, disabled: !allowed(node.id), current: current(node.id),
      })),
    ]
  }
  return [
    { id: null, name: UNSORTED, path: [], indent: 0, icon: Inbox, disabled: false, current: false },
    ...collections.map(({ node, path }) => ({ id: node.id, name: node.name, path, indent: node.depth - 1, icon: Folder, disabled: false, current: false })),
  ]
}

const firstEnabled = (targets: Target[]) => targets.findIndex(t => !t.disabled)

export function MoveToModal({ tree, title, excludeId, collectionsOnly = false, onPick, onClose }: MoveToModalProps) {
  const [search, setSearch] = useState('')
  const all = targetsOf(tree, excludeId, collectionsOnly)
  const query = search.trim().toLowerCase()
  const matches = query ? all.filter(t => t.name.toLowerCase().includes(query)) : all
  const [cursor, setCursor] = useState(() => firstEnabled(all))
  const listId = useId()
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([])
  const nestingBlocked = collectionsOnly && all.some(t => t.disabled)

  useEffect(() => {
    optionRefs.current[cursor]?.scrollIntoView?.({ block: 'nearest' })
  }, [cursor])

  const pick = (target: Target | undefined) => {
    if (!target || target.disabled) return
    if (target.current) onClose()
    else onPick(target.id, target.name)
  }

  const step = (direction: 1 | -1) => {
    for (let i = cursor + direction; i >= 0 && i < matches.length; i += direction) {
      if (!matches[i].disabled) { setCursor(i); return }
    }
  }

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); step(1) }
    if (e.key === 'ArrowUp') { e.preventDefault(); step(-1) }
    if (e.key === 'Enter') { e.preventDefault(); pick(matches[cursor]) }
  }

  const onSearch = (value: string) => {
    setSearch(value)
    const q = value.trim().toLowerCase()
    setCursor(firstEnabled(q ? all.filter(t => t.name.toLowerCase().includes(q)) : all))
  }

  const optionId = (index: number) => `${listId}-${index}`

  return (
    <Modal title={title} onClose={onClose} footer={<Button variant="link" onClick={onClose}>Cancel</Button>}>
      <Field
        autoFocus
        role="combobox"
        aria-expanded
        aria-controls={listId}
        aria-activedescendant={cursor >= 0 ? optionId(cursor) : undefined}
        placeholder="Search collections"
        value={search}
        onChange={e => onSearch(e.target.value)}
        onKeyDown={onKeyDown}
      />
      {nestingBlocked && <p className={css.moveNote}>Collections nest at most {tree.max_depth} levels deep.</p>}
      <div className={css.options} id={listId} role="listbox" aria-label={title}>
        {matches.length === 0 && <p className={css.moveEmpty}>Nothing matches “{search.trim()}”</p>}
        {matches.map((target, index) => {
          const classes = [css.option, index === cursor && css.optionOn].filter(Boolean).join(' ')
          const indent = query ? 0 : target.indent
          return (
            <button
              key={target.id ?? 'root'}
              ref={el => { optionRefs.current[index] = el }}
              id={optionId(index)}
              type="button"
              role="option"
              aria-selected={index === cursor}
              tabIndex={-1}
              disabled={target.disabled}
              className={classes}
              style={{ '--indent': indent } as CSSProperties}
              onMouseMove={() => { if (!target.disabled && index !== cursor) setCursor(index) }}
              onClick={() => pick(target)}
            >
              <span className={css.optionIcon}><Icon as={target.icon} size="s" /></span>
              <span className={css.optionName}>
                {query && target.path.length > 0 && <span className={css.optionParent}>{target.path.join(' / ')} / </span>}
                {target.name}
              </span>
              {target.current && <span className={css.optionHint}>Current</span>}
            </button>
          )
        })}
      </div>
    </Modal>
  )
}
