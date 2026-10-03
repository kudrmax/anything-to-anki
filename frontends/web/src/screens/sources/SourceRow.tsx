import { useState, type KeyboardEvent, type MouseEvent } from 'react'
import { Clapperboard, Ellipsis, FileText, Folder, Music, Pencil, RefreshCw, Sparkles, Trash2, Upload, type LucideIcon } from 'lucide-react'
import type { Collection, ContentType, GenerationStatus, ProcessingStage, SourceSummary } from '@/api/types'
import { formatDate } from '@/lib/text/format'
import { Button, Field, Icon, IconButton, Menu, Progress, Spinner, Text, type MenuItem } from '@/ui'
import css from './sources.module.css'

interface SourceRowProps {
  source: SourceSummary
  collections: Collection[]
  /** Главная строка экрана: её действие выделено. */
  primary: boolean
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

const TYPE_ICON: Record<ContentType, LucideIcon> = { text: FileText, lyrics: Music, video: Clapperboard, topic: Sparkles }
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
  idle: 'Waiting for generation',
  queued: 'Queued',
  running: 'Generating…',
  failed: 'Generation failed',
}

const stop = (e: MouseEvent) => e.stopPropagation()

/** Подпись под шкалой прогресса: что известно о фразах источника. */
function progressCaption(source: SourceSummary): string {
  if (source.candidate_count === 0) return 'Nothing to learn'
  if (source.status === 'reviewed') return `${source.learn_count} to learn`
  if (source.decided_count > 0) return `${source.decided_count} of ${source.candidate_count} decided`
  return `${source.candidate_count} phrases`
}

export function SourceRow({ source, collections, primary, onProcess, onGenerate, onCancelGeneration, onRetryGeneration, onReview, onExport, onDelete, onRename, onReprocess, onAssignCollection }: SourceRowProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(source.title)

  const isProcessing = source.status === 'processing'
  const isReviewable = source.status === 'done' || source.status === 'partially_reviewed' || source.status === 'reviewed'
  const canExport = source.status === 'partially_reviewed' || source.status === 'reviewed'
  const generation: GenerationState | null = source.awaiting_generation ? source.generation_status ?? 'idle' : null

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

  const collectionName = collections.find(c => c.id === source.collection_id)?.name ?? 'None'
  const menuItems: MenuItem[] = [
    ...(canExport ? [{ label: 'Export', icon: Upload, onSelect: () => onExport(source.id) }] : []),
    { label: 'Rename', icon: Pencil, onSelect: startEditing },
    {
      label: 'Collection',
      icon: Folder,
      value: collectionName,
      items: [
        { label: 'None', selected: source.collection_id === null, onSelect: () => onAssignCollection(source.id, null) },
        ...collections.map(c => ({ label: c.name, selected: c.id === source.collection_id, onSelect: () => onAssignCollection(source.id, c.id) })),
      ],
    },
    ...(isProcessing || source.status === 'new' ? [] : [{ label: 'Reprocess', icon: RefreshCw, onSelect: () => onReprocess(source.id) }]),
    ...(isProcessing ? [] : [{ label: 'Delete', icon: Trash2, danger: true, separated: true, onSelect: () => onDelete(source.id) }]),
  ]

  const reviewVariant = primary ? 'fill' : 'soft'
  const action = generation ? {
    idle: <Button onClick={() => onGenerate(source.id)}>Generate</Button>,
    queued: <Button variant="danger-link" onClick={() => onCancelGeneration(source.id)}>Cancel</Button>,
    running: <Button variant="danger-link" onClick={() => onCancelGeneration(source.id)}>Cancel</Button>,
    failed: <Button onClick={() => onRetryGeneration(source.id)}>Retry</Button>,
  }[generation] : {
    new: <Button onClick={() => onProcess(source.id)}>Process</Button>,
    processing: null,
    done: <Button variant={reviewVariant} onClick={() => onReview(source.id)}>Review</Button>,
    partially_reviewed: <Button variant={reviewVariant} onClick={() => onReview(source.id)}>Continue</Button>,
    reviewed: <Button variant="link" onClick={() => onReview(source.id)}>Open</Button>,
    error: <Button onClick={() => onReprocess(source.id)}>Retry</Button>,
  }[source.status]

  const progress = (() => {
    if (generation) {
      return (
        <span className={css.caption} title={source.generation_error ?? undefined}>
          {generation === 'running' && <Spinner />}
          <Text tone={generation === 'failed' ? 'err' : 'muted'} size="s">{GENERATION_LABEL[generation]}</Text>
        </span>
      )
    }
    if (isProcessing) {
      return <span className={css.caption}><Spinner /><Text tone="muted" size="s">{source.processing_stage ? STAGE_LABEL[source.processing_stage] : STAGE_DEFAULT}</Text></span>
    }
    if (source.status === 'new') return <Text tone="muted" size="s">Not processed yet</Text>
    if (source.status === 'error') return <Text tone="err" size="s">Processing failed</Text>
    const value = source.status === 'reviewed' ? 1 : source.candidate_count > 0 ? source.decided_count / source.candidate_count : 0
    return (
      <>
        <Progress value={value} />
        <Text tone="muted" size="s">{progressCaption(source)}</Text>
      </>
    )
  })()

  const classes = [css.row, isReviewable && !editing && css.clickable, source.status === 'reviewed' && css.done].filter(Boolean).join(' ')
  const tooltip = `${TYPE_LABEL[source.content_type]} · added ${formatDate(source.created_at)}${source.collection_name ? ` · ${source.collection_name}` : ''}`

  return (
    <div className={classes} title={tooltip} onClick={isReviewable && !editing ? () => onReview(source.id) : undefined}>
      <span className={css.type}><Icon as={TYPE_ICON[source.content_type]} /></span>
      <div className={css.name}>
        {editing
          ? <Field autoFocus value={draft} onChange={e => setDraft(e.target.value)} onBlur={save} onKeyDown={onKeyDown} onClick={stop} />
          : <span className={css.title} onDoubleClick={e => { e.stopPropagation(); startEditing() }}>{source.title}</span>}
      </div>
      <div className={css.progress}>{progress}</div>
      <div className={css.action} onClick={stop}>{action}</div>
      <div className={css.more} onClick={stop}>
        <Menu trigger={<IconButton icon={Ellipsis} label="More" />} items={menuItems} />
      </div>
    </div>
  )
}
