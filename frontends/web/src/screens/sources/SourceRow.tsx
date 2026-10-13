import { useState, type DragEvent, type KeyboardEvent, type MouseEvent } from 'react'
import { BookOpen, Clapperboard, Ellipsis, FileText, FolderInput, Globe, Music, Pencil, RefreshCw, Sparkles, Trash2, Upload, type LucideIcon } from 'lucide-react'
import type { GenerationStatus, ProcessingStage, SourceSummary } from '@/api/types'
import { formatDate } from '@/lib/text/format'
import { Button, Field, Icon, IconButton, Menu, Progress, Spinner, Text, type MenuItem } from '@/ui'
import { SOURCES_MIME } from './CollectionTree'
import css from './sources.module.css'

interface SourceRowProps {
  source: SourceSummary
  selected: boolean
  /** Путь узла под названием: источник лежит не прямо в открытом узле. */
  showPath: boolean
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
  /** true — клик ушёл на выбор строки, открывать источник не нужно. */
  onRowClick: (e: MouseEvent, id: number) => boolean
  onMoveTo: (id: number) => void
  /** Что тащим: выбор, если строка в нём, иначе только её. */
  dragIds: () => number[]
}

type SourceLook = 'text' | 'book' | 'lyrics' | 'video' | 'topic' | 'phrases'

const TYPE_ICON: Record<SourceLook, LucideIcon> = { text: FileText, book: BookOpen, lyrics: Music, video: Clapperboard, topic: Sparkles, phrases: Globe }
const TYPE_LABEL: Record<SourceLook, string> = { text: 'Text', book: 'Book', lyrics: 'Lyrics', video: 'Video', topic: 'Topic', phrases: 'Phrases' }

const lookOf = (source: SourceSummary): SourceLook => {
  if (source.role === 'topic') return 'topic'
  if (source.role === 'saved_phrases') return 'phrases'
  if (source.has_video) return 'video'
  if (source.kind === 'book') return 'book'
  return source.kind === 'song' ? 'lyrics' : 'text'
}

const STAGE_LABEL: Record<ProcessingStage, string> = {
  analyzing_text: 'Analyzing text…',
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

export function SourceRow({ source, selected, showPath, primary, onProcess, onGenerate, onCancelGeneration, onRetryGeneration, onReview, onExport, onDelete, onRename, onReprocess, onRowClick, onMoveTo, dragIds }: SourceRowProps) {
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

  const menuItems: MenuItem[] = [
    ...(canExport ? [{ label: 'Export', icon: Upload, onSelect: () => onExport(source.id) }] : []),
    { label: 'Rename', icon: Pencil, onSelect: startEditing },
    { label: 'Move to…', icon: FolderInput, onSelect: () => onMoveTo(source.id) },
    ...(isProcessing || source.status === 'new' || source.is_permanent ? [] : [{ label: 'Reprocess', icon: RefreshCw, onSelect: () => onReprocess(source.id) }]),
    ...(isProcessing || source.is_permanent ? [] : [{ label: 'Delete', icon: Trash2, danger: true, separated: true, onSelect: () => onDelete(source.id) }]),
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

  const classes = [css.row, isReviewable && !editing && css.clickable, source.status === 'reviewed' && css.done, selected && css.selected].filter(Boolean).join(' ')
  const look = lookOf(source)
  const tooltip = `${TYPE_LABEL[look]} · added ${formatDate(source.created_at)}${source.collection_path.length ? ` · ${source.collection_path.join(' / ')}` : ''}`

  const onClick = (e: MouseEvent) => {
    if (onRowClick(e, source.id)) return
    if (isReviewable && !editing) onReview(source.id)
  }
  const onDragStart = (e: DragEvent) => {
    e.dataTransfer.setData(SOURCES_MIME, JSON.stringify(dragIds()))
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className={classes} title={tooltip} aria-selected={selected} draggable={!editing} onDragStart={onDragStart} onClick={onClick}>
      <span className={css.type}><Icon as={TYPE_ICON[look]} /></span>
      <div className={css.name}>
        {editing
          ? <Field autoFocus value={draft} onChange={e => setDraft(e.target.value)} onBlur={save} onKeyDown={onKeyDown} onClick={stop} />
          : <span className={css.title} onDoubleClick={e => { e.stopPropagation(); startEditing() }}>{source.title}</span>}
        {showPath && source.collection_path.length > 0 && <span className={css.path}>{source.collection_path.at(-1)}</span>}
      </div>
      <div className={css.progress}>{progress}</div>
      <div className={css.action} onClick={stop}>{action}</div>
      <div className={css.more} onClick={stop}>
        <Menu trigger={<IconButton icon={Ellipsis} label="More" />} items={menuItems} />
      </div>
    </div>
  )
}
