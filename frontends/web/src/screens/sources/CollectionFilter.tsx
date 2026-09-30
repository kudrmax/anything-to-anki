import { useState, type KeyboardEvent } from 'react'
import type { Collection } from '@/api/types'
import { Button, Chip, Field, Menu } from '@/ui'

interface CollectionFilterProps {
  collections: Collection[]
  activeId: number | null
  onSelect: (id: number | null) => void
  onCreate: (name: string) => void
  onRename: (id: number, name: string) => void
  onDelete: (id: number) => void
}

export function CollectionFilter({ collections, activeId, onSelect, onCreate, onRename, onDelete }: CollectionFilterProps) {
  const [creating, setCreating] = useState(false)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [draft, setDraft] = useState('')

  const submit = () => {
    const name = draft.trim()
    if (!name) return
    if (renamingId !== null) onRename(renamingId, name)
    else onCreate(name)
    cancel()
  }
  const cancel = () => { setCreating(false); setRenamingId(null); setDraft('') }
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') submit()
    if (e.key === 'Escape') cancel()
  }
  const input = <Field autoFocus value={draft} placeholder="Collection name…" onChange={e => setDraft(e.target.value)} onKeyDown={onKeyDown} onBlur={cancel} />

  return (
    <>
      <Chip on={activeId === null} onClick={() => onSelect(null)}>All</Chip>
      {collections.map(collection => renamingId === collection.id ? (
        <span key={collection.id}>{input}</span>
      ) : (
        <Menu
          key={collection.id}
          openOn="contextmenu"
          align="start"
          trigger={
            <Chip on={activeId === collection.id} onClick={() => onSelect(collection.id)}>
              {collection.name} ({collection.source_count})
            </Chip>
          }
          items={[
            { label: 'Rename', onSelect: () => { setDraft(collection.name); setRenamingId(collection.id) } },
            { label: 'Delete collection', danger: true, onSelect: () => onDelete(collection.id) },
          ]}
        />
      ))}
      {creating ? input : <Button variant="link" onClick={() => setCreating(true)}>+ Collection</Button>}
    </>
  )
}
