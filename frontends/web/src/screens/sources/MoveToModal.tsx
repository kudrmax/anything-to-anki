import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { Folder, FolderTree, Inbox, type LucideIcon } from 'lucide-react'
import type { CollectionNode, CollectionTree } from '@/api/types'
import { Button, Field, Icon, Modal } from '@/ui'
import css from './sources.module.css'

interface MoveToModalProps {
  tree: CollectionTree
  title: string
  /** Узел, которого нет среди целей: сама переносимая коллекция. */
  excludeId?: number
  /** Переносим коллекцию: цели — верхний уровень и коллекции, принимающие подколлекции. */
  collectionsOnly?: boolean
  onPick: (collectionId: number | null, name: string) => void
  onClose: () => void
}

interface Target {
  id: number | null
  name: string
  parent: string | null
  icon: LucideIcon
  disabled: boolean
  current: boolean
}

const TOP_LEVEL = 'Top level'
const UNSORTED = 'Unsorted'

function findNode(nodes: CollectionNode[], id: number): CollectionNode | undefined {
  for (const node of nodes) {
    if (node.id === id) return node
    const child = findNode(node.children, id)
    if (child) return child
  }
  return undefined
}

function targetsOf(tree: CollectionTree, excludeId: number | undefined, collectionsOnly: boolean): Target[] {
  const target = (node: CollectionNode, parent: string | null, disabled = false, current = false): Target =>
    ({ id: node.id, name: node.name, parent, icon: Folder, disabled, current })

  if (collectionsOnly) {
    const moving = excludeId === undefined ? undefined : findNode(tree.collections, excludeId)
    const nestable = moving?.can_be_nested ?? true
    return [
      { id: null, name: TOP_LEVEL, parent: null, icon: FolderTree, disabled: false, current: moving?.parent_id === null },
      ...tree.collections
        .filter(node => node.accepts_collections && node.id !== excludeId)
        .map(node => target(node, null, !nestable, node.id === moving?.parent_id)),
    ]
  }
  return [
    { id: null, name: UNSORTED, parent: null, icon: Inbox, disabled: false, current: false },
    ...tree.collections.filter(node => node.id !== excludeId).flatMap(node => [
      target(node, null),
      ...node.children.filter(child => child.id !== excludeId).map(child => target(child, node.name)),
    ]),
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
    if (target && !target.disabled) onPick(target.id, target.name)
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
      {nestingBlocked && <p className={css.moveNote}>A collection with subcollections can only stay at the top level.</p>}
      <div className={css.options} id={listId} role="listbox" aria-label={title}>
        {matches.length === 0 && <p className={css.moveEmpty}>Nothing matches “{search.trim()}”</p>}
        {matches.map((target, index) => {
          const nested = target.parent !== null
          const classes = [css.option, nested && !query && css.optionSub, index === cursor && css.optionOn].filter(Boolean).join(' ')
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
              onMouseMove={() => { if (!target.disabled && index !== cursor) setCursor(index) }}
              onClick={() => pick(target)}
            >
              <span className={css.optionIcon}><Icon as={target.icon} size="s" /></span>
              <span className={css.optionName}>
                {nested && query && <span className={css.optionParent}>{target.parent} / </span>}
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
