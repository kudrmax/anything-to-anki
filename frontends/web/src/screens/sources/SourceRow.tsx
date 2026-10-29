import { useRef, useState, type DragEvent, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react'
import { BookOpen, Clapperboard, Ellipsis, FileText, Globe, Music, Sparkles, type LucideIcon } from 'lucide-react'
import type { GenerationStatus, SetOperation, SourceSummary } from '@/api/types'
import { formatDate, TOOLTIP_LINE } from '@/lib/text/format'
import { Button, Field, Icon, IconButton, Menu, Progress, Spinner, Text } from '@/ui'
import { SOURCES_MIME } from './CollectionTree'
import { setStackDragImage } from './dragStack'
import { ReviewAction } from './ReviewAction'
import { scopeMenuItems } from './scopeMenu'
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
  /** Rebuild или Refresh: какую из available_operations выбрали. */
  onOperation: (id: number, operation: SetOperation) => void
  /** true — клик ушёл на выбор строки, открывать источник не нужно. */
  onRowClick: (e: MouseEvent, id: number) => boolean
  onMoveTo: (id: number) => void
  /** Что тащим: выбор, если строка в нём, иначе только её. */
  dragIds: () => number[]
  /** На телефоне перетаскивания нет. */
  draggable: boolean
  /** Долгий тап на телефоне включает выбор. */
  onLongPress: (id: number) => void
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

type GenerationState = GenerationStatus | 'idle'

const GENERATION_LABEL: Record<GenerationState, string> = {
  idle: 'Waiting for generation',
  queued: 'Queued',
  running: 'Generating…',
  failed: 'Generation failed',
}

const stop = (e: MouseEvent) => e.stopPropagation()
const LONG_PRESS_MS = 500
const TOUCH = 'touch'

export function SourceRow({ source, selected, showPath, primary, onProcess, onGenerate, onCancelGeneration, onRetryGeneration, onReview, onExport, onDelete, onRename, onOperation, onRowClick, onMoveTo, dragIds, draggable, onLongPress }: SourceRowProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(source.title)
  const pressTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Тап, которым закончился долгий тап, уже включил выбор: открывать источник не нужно.
  const longPressed = useRef(false)

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

  const menuItems = scopeMenuItems(source, {
    onExport: () => onExport(source.id),
    onOperation: operation => onOperation(source.id, operation),
    onRename: startEditing,
    onMoveTo: () => onMoveTo(source.id),
    onDelete: source.can_delete ? () => onDelete(source.id) : undefined,
  })

  const action = generation ? {
    idle: <Button onClick={() => onGenerate(source.id)}>Generate</Button>,
    queued: <Button variant="danger-link" onClick={() => onCancelGeneration(source.id)}>Cancel</Button>,
    running: <Button variant="danger-link" onClick={() => onCancelGeneration(source.id)}>Cancel</Button>,
    failed: <Button onClick={() => onRetryGeneration(source.id)}>Retry</Button>,
  }[generation] : (
    <ReviewAction
      status={source.status}
      canProcess={source.can_process}
      canReview={source.can_review}
      primary={primary}
      onProcess={() => onProcess(source.id)}
      onReview={() => onReview(source.id)}
    />
  )

  const progress = (() => {
    if (generation) {
      return (
        <span className={css.caption} title={source.generation_error ?? undefined}>
          {generation === 'running' && <Spinner />}
          <Text tone={generation === 'failed' ? 'err' : 'muted'} size="s">{GENERATION_LABEL[generation]}</Text>
        </span>
      )
    }
    if (source.status === 'new') return <Text tone="muted" size="s">Not processed yet</Text>
    if (source.status === 'error') return <Text tone="err" size="s">Processing failed</Text>
    return (
      <>
        <Progress value={source.review_fraction} />
        <span className={css.caption}>
          {source.busy_with && <Spinner />}
          <Text tone="muted" size="s">{source.progress_caption}</Text>
        </span>
      </>
    )
  })()

  const classes = [css.row, source.can_review && !editing && css.clickable, source.status === 'reviewed' && css.done, selected && css.selected].filter(Boolean).join(' ')
  const look = lookOf(source)
  const tooltip = [
    TYPE_LABEL[look],
    `Added ${formatDate(source.created_at)}`,
    ...(source.collection_path.length ? [source.collection_path.join(' / ')] : []),
  ].join(TOOLTIP_LINE)

  const cancelPress = () => {
    if (pressTimer.current) clearTimeout(pressTimer.current)
    pressTimer.current = null
  }
  const onPointerDown = (e: PointerEvent) => {
    if (e.pointerType !== TOUCH || editing) return
    longPressed.current = false
    cancelPress()
    pressTimer.current = setTimeout(() => {
      pressTimer.current = null
      longPressed.current = true
      onLongPress(source.id)
    }, LONG_PRESS_MS)
  }
  const onContextMenu = (e: MouseEvent) => { if (pressTimer.current || longPressed.current) e.preventDefault() }

  const onClick = (e: MouseEvent) => {
    if (longPressed.current) { longPressed.current = false; return }
    if (onRowClick(e, source.id)) return
    if (source.can_review && !editing) onReview(source.id)
  }
  const onDragStart = (e: DragEvent) => {
    const ids = dragIds()
    e.dataTransfer.setData(SOURCES_MIME, JSON.stringify(ids))
    e.dataTransfer.effectAllowed = 'move'
    if (ids.length > 1) setStackDragImage(e, e.currentTarget as HTMLElement, ids.length)
  }

  return (
    <div
      className={classes}
      title={tooltip}
      role="option"
      aria-selected={selected}
      draggable={draggable && !editing}
      onDragStart={onDragStart}
      onClick={onClick}
      onPointerDown={onPointerDown}
      onPointerUp={cancelPress}
      onPointerCancel={cancelPress}
      onPointerLeave={cancelPress}
      onContextMenu={onContextMenu}
    >
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
