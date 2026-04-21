import { useState, useRef, useEffect } from 'react'
import { Loader2, Pencil, RefreshCw, Trash2 } from 'lucide-react'
import type { ProcessingStage, SourceStatus, SourceSummary } from '@/api/types'

interface SourceCardProps {
  source: SourceSummary
  onProcess: (id: number) => void
  onReview: (id: number) => void
  onExport: (id: number) => void
  onDelete: (id: number) => void
  onRename: (id: number, title: string) => void
  onReprocess: (id: number) => void
  isProcessingLocal: boolean
}

const STATUS_BADGE: Record<SourceStatus, { label: string; bg: string; color: string }> = {
  new:                { label: 'New',        bg: 'var(--src-new-bg)',        color: 'var(--src-new)' },
  processing:         { label: 'Processing', bg: 'var(--src-processing-bg)', color: 'var(--src-processing)' },
  done:               { label: 'Ready for review', bg: 'var(--src-done-bg)', color: 'var(--src-done)' },
  error:              { label: 'Error',      bg: 'var(--src-error-bg)',      color: 'var(--src-error)' },
  partially_reviewed: { label: 'In Review',  bg: 'var(--src-in-review-bg)',  color: 'var(--src-in-review)' },
  reviewed:           { label: 'Reviewed',   bg: 'var(--src-reviewed-bg)',   color: 'var(--src-reviewed)' },
}

const STATUS_BORDER: Record<SourceStatus, { grad: string; glow: string }> = {
  new:                { grad: 'linear-gradient(to bottom, color-mix(in srgb, var(--src-new) 40%, transparent), color-mix(in srgb, var(--src-new) 10%, transparent))',  glow: '' },
  processing:         { grad: 'linear-gradient(to bottom, color-mix(in srgb, var(--src-processing) 80%, transparent), color-mix(in srgb, var(--src-processing) 30%, transparent))',    glow: '0 0 8px color-mix(in srgb, var(--src-processing) 40%, transparent)' },
  done:               { grad: 'linear-gradient(to bottom, color-mix(in srgb, var(--src-done) 80%, transparent), color-mix(in srgb, var(--src-done) 30%, transparent))',    glow: '0 0 8px color-mix(in srgb, var(--src-done) 40%, transparent)' },
  error:              { grad: 'linear-gradient(to bottom, color-mix(in srgb, var(--src-error) 80%, transparent), color-mix(in srgb, var(--src-error) 30%, transparent))',    glow: '0 0 8px color-mix(in srgb, var(--src-error) 40%, transparent)' },
  partially_reviewed: { grad: 'linear-gradient(to bottom, color-mix(in srgb, var(--src-in-review) 80%, transparent), color-mix(in srgb, var(--src-in-review) 30%, transparent))',    glow: '0 0 8px color-mix(in srgb, var(--src-in-review) 40%, transparent)' },
  reviewed:           { grad: 'linear-gradient(to bottom, color-mix(in srgb, var(--src-reviewed) 80%, transparent), color-mix(in srgb, var(--src-reviewed) 30%, transparent))',    glow: '0 0 8px color-mix(in srgb, var(--src-reviewed) 40%, transparent)' },
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  return d.toLocaleDateString()
}

const STAGE_LABELS: Record<ProcessingStage, string> = {
  cleaning_source: 'Cleaning source format…',
  analyzing_text: 'Analyzing text…',
}

const GHOST_BTN = {
  background: 'var(--abg)',
  color: 'var(--accent)',
  border: '1px solid var(--glass-b)',
} as const

export function SourceCard({ source, onProcess, onReview, onExport, onDelete, onRename, onReprocess, isProcessingLocal }: SourceCardProps) {
  const badge = STATUS_BADGE[source.status]
  const border = STATUS_BORDER[source.status]
  const isProcessing = source.status === 'processing' || isProcessingLocal
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(source.title)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing) inputRef.current?.focus()
  }, [isEditing])

  const handleSave = () => {
    const trimmed = editValue.trim()
    if (trimmed && trimmed !== source.title) {
      onRename(source.id, trimmed)
    }
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') {
      setEditValue(source.title)
      setIsEditing(false)
    }
  }
  const reviewProgress = source.candidate_count > 0
    ? (source.learn_count / source.candidate_count) * 100
    : 0

  const isReviewable = source.status === 'done' || source.status === 'partially_reviewed' || source.status === 'reviewed'

  return (
    <div
      className={`group glass-card rounded-2xl px-5 py-[18px] flex items-start gap-3 relative overflow-hidden${isReviewable ? ' cursor-pointer' : ''}`}
      onClick={isReviewable ? () => onReview(source.id) : undefined}
    >
      {/* Left status border */}
      <div
        className="absolute left-0 top-[15%] bottom-[15%] w-[2px] rounded-full"
        style={{ background: border.grad, boxShadow: border.glow || undefined }}
      />

      {/* Spinner for processing */}
      {isProcessing && (
        <div className="mt-0.5 shrink-0">
          <Loader2 size={14} className="animate-spin" style={{ color: 'var(--src-processing)' }} />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col gap-1">
        <div className="flex items-center gap-1.5 min-w-0">
          {isEditing ? (
            <input
              ref={inputRef}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={handleSave}
              onKeyDown={handleKeyDown}
              className="text-sm font-semibold leading-snug w-full rounded px-1 py-0.5"
              style={{
                color: 'var(--text)',
                background: 'var(--ibg)',
                border: '1.5px solid var(--ib)',
                outline: 'none',
              }}
            />
          ) : (
            <>
              <p className="text-sm font-semibold leading-snug line-clamp-2" style={{ color: 'var(--text)' }}>
                {source.title}
              </p>
              {!isProcessing && (
                <button
                  onClick={(e) => { e.stopPropagation(); setEditValue(source.title); setIsEditing(true) }}
                  className="cursor-pointer shrink-0 opacity-0 group-hover:opacity-40 hover:!opacity-100 transition-opacity"
                  style={{ background: 'transparent', border: 'none', padding: 0, lineHeight: 0 }}
                  title="Rename"
                >
                  <Pencil size={12} style={{ color: 'var(--tm)' }} />
                </button>
              )}
            </>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs mt-0.5">
          <span style={{ color: 'var(--tm)' }}>{formatDate(source.created_at)}</span>
          {source.source_type === 'lyrics_pasted' && (
            <span
              className="px-1.5 py-0.5 rounded text-[10px] font-medium"
              style={{ background: 'var(--src-lyrics-bg)', color: 'var(--src-lyrics)' }}
            >
              lyrics
            </span>
          )}

          {isProcessing && (
            <span style={{ color: 'var(--tm)' }}>
              {source.processing_stage
                ? STAGE_LABELS[source.processing_stage]
                : 'Starting…'}
            </span>
          )}

          {/* "Nothing to learn" from master — functional addition */}
          {source.status === 'done' && source.candidate_count === 0 && !isProcessing && (
            <span style={{ color: 'var(--td)', fontStyle: 'italic' }}>Nothing to learn</span>
          )}

          {source.candidate_count > 0 && !isProcessing && (
            <>
              {source.status === 'partially_reviewed' && (
                <span style={{ color: 'var(--src-in-review)', fontWeight: 600 }}>
                  {source.learn_count} / {source.candidate_count} to learn
                </span>
              )}
              {source.status === 'done' && (
                <span style={{ color: 'var(--src-done)', fontWeight: 600 }}>
                  {source.candidate_count} candidates
                </span>
              )}
              {source.status === 'reviewed' && (
                <span style={{ color: 'var(--src-reviewed)', fontWeight: 600 }}>
                  {source.candidate_count} cards
                </span>
              )}
            </>
          )}
        </div>

        {/* Review progress bar */}
        {source.status === 'partially_reviewed' && source.candidate_count > 0 && (
          <div
            className="mt-2 h-[3px] rounded-full overflow-hidden"
            style={{ background: 'color-mix(in srgb, var(--src-in-review) 12%, transparent)' }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${reviewProgress}%`,
                background: `linear-gradient(90deg, color-mix(in srgb, var(--src-in-review) 80%, transparent), color-mix(in srgb, var(--src-in-review) 50%, transparent))`,
              }}
            />
          </div>
        )}
      </div>

      {/* Right: badge + action button */}
      <div className="flex flex-col items-end gap-2 shrink-0">
        <div className="flex items-center gap-2">
          <span
            className="text-[11px] font-semibold px-2.5 py-1 rounded-full whitespace-nowrap"
            style={{ background: badge.bg, color: badge.color }}
          >
            {badge.label}
          </span>
          {!isProcessing && (source.status === 'done' || source.status === 'partially_reviewed' || source.status === 'reviewed' || source.status === 'error') && (
            <button
              onClick={(e) => { e.stopPropagation(); onReprocess(source.id) }}
              className="cursor-pointer transition-opacity hover:opacity-100 opacity-40"
              style={{ background: 'transparent', border: 'none', padding: 0, lineHeight: 0 }}
              title="Reprocess source"
            >
              <RefreshCw size={13} style={{ color: 'var(--fg-muted)' }} />
            </button>
          )}
          {!isProcessing && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(source.id) }}
              className="cursor-pointer transition-opacity hover:opacity-100 opacity-40"
              style={{ background: 'transparent', border: 'none', padding: 0, lineHeight: 0 }}
              title="Delete source"
            >
              <Trash2 size={13} style={{ color: 'var(--src-error)' }} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {source.status === 'partially_reviewed' && (
            <button
              onClick={(e) => { e.stopPropagation(); onExport(source.id) }}
              className="glass-pill text-xs font-medium cursor-pointer"
              style={{ ...GHOST_BTN, padding: '5px 11px' }}
            >
              Export →
            </button>
          )}
          {source.status === 'reviewed' && (
            <button
              onClick={(e) => { e.stopPropagation(); onExport(source.id) }}
              className="glass-pill text-xs font-medium cursor-pointer"
              style={{ ...GHOST_BTN, padding: '5px 11px' }}
            >
              Export →
            </button>
          )}
          {source.status === 'new' && (
            <button
              onClick={(e) => { e.stopPropagation(); onProcess(source.id) }}
              disabled={isProcessingLocal}
              className="glass-pill text-xs font-medium disabled:opacity-50 cursor-pointer"
              style={{ ...GHOST_BTN, padding: '5px 11px' }}
            >
              Process →
            </button>
          )}
          {(source.status === 'done' || source.status === 'partially_reviewed' || source.status === 'reviewed') && (
            <button
              onClick={(e) => { e.stopPropagation(); onReview(source.id) }}
              className="glass-pill text-xs font-medium cursor-pointer"
              style={{ ...GHOST_BTN, padding: '5px 11px' }}
            >
              Review →
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
