import { useState, type KeyboardEvent } from 'react'
import { RefreshCw, Trash2 } from 'lucide-react'
import type { Collection, ContentType, ProcessingStage, SourceStatus, SourceSummary } from '@/api/types'
import { formatDate } from '@/lib/text/format'
import { Button, Field, IconButton, Menu, Row, Text, type MenuItem, type Tone } from '@/ui'

interface SourceRowProps {
  source: SourceSummary
  collections: Collection[]
  onProcess: (id: number) => void
  onReview: (id: number) => void
  onExport: (id: number) => void
  onDelete: (id: number) => void
  onRename: (id: number, title: string) => void
  onReprocess: (id: number) => void
  onAssignCollection: (sourceId: number, collectionId: number | null) => void
}

const STATUS_LABEL: Record<SourceStatus, string> = {
  new: 'New',
  processing: 'Processing',
  done: 'Ready for review',
  error: 'Error',
  partially_reviewed: 'In review',
  reviewed: 'Reviewed',
}

const STATUS_TONE: Record<SourceStatus, Tone> = {
  new: 'idle',
  processing: 'run',
  done: 'ok',
  error: 'err',
  partially_reviewed: 'accent',
  reviewed: 'off',
}

const TYPE_LABEL: Record<ContentType, string> = { text: 'Text', lyrics: 'Lyrics', video: 'Video' }

const STAGE_LABEL: Record<ProcessingStage, string> = {
  cleaning_source: 'Cleaning source format…',
  analyzing_text: 'Analyzing text…',
}
const STAGE_DEFAULT = 'Starting…'

function countText(source: SourceSummary): string | null {
  if (source.status === 'done' && source.candidate_count === 0) return 'Nothing to learn'
  if (source.candidate_count === 0) return null
  if (source.status === 'partially_reviewed') return `${source.learn_count} / ${source.candidate_count} to learn`
  if (source.status === 'done') return `${source.candidate_count} candidates`
  if (source.status === 'reviewed') return `${source.candidate_count} cards`
  return null
}

export function SourceRow({ source, collections, onProcess, onReview, onExport, onDelete, onRename, onReprocess, onAssignCollection }: SourceRowProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(source.title)

  const isProcessing = source.status === 'processing'
  const isReviewable = source.status === 'done' || source.status === 'partially_reviewed' || source.status === 'reviewed'

  const startEditing = () => { setDraft(source.title); setEditing(true) }
  const save = () => {
    const title = draft.trim()
    if (title && title !== source.title) onRename(source.id, title)
    setEditing(false)
  }
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') save()
    if (e.key === 'Escape') setEditing(false)
  }

  const collectionItems: MenuItem[] = [
    { label: 'No collection', selected: source.collection_id === null, onSelect: () => onAssignCollection(source.id, null) },
    ...collections.map(c => ({
      label: c.name,
      selected: c.id === source.collection_id,
      onSelect: () => onAssignCollection(source.id, c.id),
    })),
  ]

  const details = isProcessing
    ? [source.processing_stage ? STAGE_LABEL[source.processing_stage] : STAGE_DEFAULT]
    : [countText(source), formatDate(source.created_at)].filter((part): part is string => part !== null)

  const title = editing
    ? <Field autoFocus value={draft} onChange={e => setDraft(e.target.value)} onBlur={save} onKeyDown={onKeyDown} onClick={e => e.stopPropagation()} />
    : <span onDoubleClick={e => { e.stopPropagation(); startEditing() }} title="Double-click to rename">{source.title}</span>

  const collectionMenu = (
    <>
      {' · '}
      <Menu
        align="start"
        trigger={<Button variant="link">{source.collection_name ?? '+ collection'}</Button>}
        items={collectionItems}
      />
    </>
  )
  const summary = [TYPE_LABEL[source.content_type], ...details].join(' · ')

  const action = {
    new: <Button onClick={() => onProcess(source.id)}>Process</Button>,
    processing: null,
    done: <Button onClick={() => onReview(source.id)}>Review</Button>,
    partially_reviewed: <Button onClick={() => onReview(source.id)}>Continue</Button>,
    reviewed: <Button onClick={() => onReview(source.id)}>Open</Button>,
    error: <Button onClick={() => onReprocess(source.id)}>Retry</Button>,
  }[source.status]

  const canExport = source.status === 'partially_reviewed' || source.status === 'reviewed'

  return (
    <Row
      tone={STATUS_TONE[source.status]}
      dim={source.status === 'reviewed'}
      title={title}
      meta={source.collection_name ? <>{summary}{collectionMenu}</> : summary}
      hoverMeta={source.collection_name ? undefined : collectionMenu}
      onClick={isReviewable && !editing ? () => onReview(source.id) : undefined}
      actions={!isProcessing && (
        <>
          {source.status !== 'new' && <IconButton icon={RefreshCw} label="Reprocess" onClick={() => onReprocess(source.id)} />}
          <IconButton icon={Trash2} label="Delete" onClick={() => onDelete(source.id)} />
        </>
      )}
      trailing={
        <>
          <Text tone={source.status === 'error' ? 'err' : 'muted'}>{STATUS_LABEL[source.status]}</Text>
          {canExport && <Button variant="link" onClick={() => onExport(source.id)}>Export</Button>}
          {action}
        </>
      }
    />
  )
}
