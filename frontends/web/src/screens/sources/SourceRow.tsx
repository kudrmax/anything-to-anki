import { useState, type KeyboardEvent } from 'react'
import { RefreshCw, Trash2 } from 'lucide-react'
import type { Collection, ContentType, GenerationStatus, ProcessingStage, SourceStatus, SourceSummary } from '@/api/types'
import { formatDate } from '@/lib/text/format'
import { Button, Field, IconButton, Menu, Row, Text, type MenuItem, type Tone } from '@/ui'

interface SourceRowProps {
  source: SourceSummary
  collections: Collection[]
  onProcess: (id: number) => void
  onGenerate: (id: number) => void
  onCancelGeneration: (id: number) => void
  onRetryGeneration: (id: number) => void
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

const TYPE_LABEL: Record<ContentType, string> = { text: 'Text', lyrics: 'Lyrics', video: 'Video', topic: 'Topic' }

const STAGE_LABEL: Record<ProcessingStage, string> = {
  cleaning_source: 'Cleaning source format…',
  analyzing_text: 'Analyzing text…',
  mapping_timecodes: 'Mapping timecodes…',
  collecting_phrases: 'Collecting phrases…',
}
const STAGE_DEFAULT = 'Starting…'

type GenerationState = GenerationStatus | 'idle'

const GENERATION_LABEL: Record<GenerationState, string> = {
  idle: 'New',
  queued: 'Queued',
  running: 'Generating…',
  failed: 'Generation failed',
}

const GENERATION_TONE: Record<GenerationState, Tone> = {
  idle: 'idle',
  queued: 'idle',
  running: 'run',
  failed: 'err',
}

function countText(source: SourceSummary): string | null {
  if (source.status === 'done' && source.candidate_count === 0) return 'Nothing to learn'
  if (source.candidate_count === 0) return null
  if (source.status === 'partially_reviewed') return `${source.learn_count} / ${source.candidate_count} to learn`
  if (source.status === 'done') return `${source.candidate_count} candidates`
  if (source.status === 'reviewed') return `${source.candidate_count} cards`
  return null
}

export function SourceRow({ source, collections, onProcess, onGenerate, onCancelGeneration, onRetryGeneration, onReview, onExport, onDelete, onRename, onReprocess, onAssignCollection }: SourceRowProps) {
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

  const generation: GenerationState | null = source.awaiting_generation ? source.generation_status ?? 'idle' : null
  const generationAction = generation && {
    idle: <Button onClick={() => onGenerate(source.id)}>Generate</Button>,
    queued: <Button variant="danger-link" onClick={() => onCancelGeneration(source.id)}>Cancel</Button>,
    running: <Button variant="danger-link" onClick={() => onCancelGeneration(source.id)}>Cancel</Button>,
    failed: <Button onClick={() => onRetryGeneration(source.id)}>Retry</Button>,
  }[generation]
  const statusLabel = generation
    ? <span title={source.generation_error ?? undefined}><Text tone={generation === 'failed' ? 'err' : 'muted'}>{GENERATION_LABEL[generation]}</Text></span>
    : <Text tone={source.status === 'error' ? 'err' : 'muted'}>{STATUS_LABEL[source.status]}</Text>

  return (
    <Row
      tone={generation ? GENERATION_TONE[generation] : STATUS_TONE[source.status]}
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
          {statusLabel}
          {canExport && <Button variant="link" onClick={() => onExport(source.id)}>Export</Button>}
          {generationAction ?? action}
        </>
      }
    />
  )
}
