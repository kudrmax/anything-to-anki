import { Loader2 } from 'lucide-react'
import type { SourceStatus, SourceSummary } from '@/api/types'

interface SourceCardProps {
  source: SourceSummary
  onProcess: (id: number) => void
  onReview: (id: number) => void
  onExport: (id: number) => void
  isProcessingLocal: boolean
}

const STATUS_BADGE: Record<SourceStatus, { label: string; bg: string; color: string }> = {
  new:                { label: 'New',        bg: 'rgba(148,163,184,.13)', color: 'rgba(148,163,184,.9)' },
  processing:         { label: 'Processing', bg: 'rgba(245,158,11,.13)',  color: 'rgba(245,158,11,.95)' },
  done:               { label: 'Ready',      bg: 'rgba(16,185,129,.13)',  color: 'rgba(16,185,129,.95)' },
  error:              { label: 'Error',      bg: 'rgba(244,63,94,.13)',   color: 'rgba(244,63,94,.95)' },
  partially_reviewed: { label: 'In Review',  bg: 'rgba(249,115,22,.13)', color: 'rgba(249,115,22,.95)' },
  reviewed:           { label: 'Reviewed',   bg: 'rgba(14,165,233,.13)',  color: 'rgba(14,165,233,.95)' },
}

const STATUS_BORDER: Record<SourceStatus, { grad: string; glow: string }> = {
  new:                { grad: 'linear-gradient(to bottom, rgba(148,163,184,.4), rgba(148,163,184,.1))',  glow: '' },
  processing:         { grad: 'linear-gradient(to bottom, rgba(245,158,11,.8), rgba(251,191,36,.3))',    glow: '0 0 8px rgba(245,158,11,.4)' },
  done:               { grad: 'linear-gradient(to bottom, rgba(16,185,129,.8), rgba(52,211,153,.3))',    glow: '0 0 8px rgba(16,185,129,.4)' },
  error:              { grad: 'linear-gradient(to bottom, rgba(244,63,94,.8), rgba(251,113,133,.3))',    glow: '0 0 8px rgba(244,63,94,.4)' },
  partially_reviewed: { grad: 'linear-gradient(to bottom, rgba(249,115,22,.8), rgba(251,146,60,.3))',    glow: '0 0 8px rgba(249,115,22,.4)' },
  reviewed:           { grad: 'linear-gradient(to bottom, rgba(14,165,233,.8), rgba(56,189,248,.3))',    glow: '0 0 8px rgba(14,165,233,.4)' },
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

const GHOST_BTN = {
  background: 'var(--abg)',
  color: 'var(--accent)',
  border: '1px solid var(--glass-b)',
} as const

export function SourceCard({ source, onProcess, onReview, onExport, isProcessingLocal }: SourceCardProps) {
  const badge = STATUS_BADGE[source.status]
  const border = STATUS_BORDER[source.status]
  const isProcessing = source.status === 'processing' || isProcessingLocal
  const reviewProgress = source.candidate_count > 0
    ? (source.learn_count / source.candidate_count) * 100
    : 0

  return (
    <div className="glass-card rounded-2xl px-5 py-[18px] flex items-start gap-3 relative overflow-hidden">
      {/* Left status border */}
      <div
        className="absolute left-0 top-[15%] bottom-[15%] w-[2px] rounded-full"
        style={{ background: border.grad, boxShadow: border.glow || undefined }}
      />

      {/* Spinner for processing */}
      {isProcessing && (
        <div className="mt-0.5 shrink-0">
          <Loader2 size={14} className="animate-spin" style={{ color: 'rgba(245,158,11,.95)' }} />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col gap-1">
        <p className="text-sm font-semibold leading-snug line-clamp-2" style={{ color: 'var(--text)' }}>
          {source.raw_text_preview}
        </p>

        <div className="flex items-center gap-2 text-xs mt-0.5">
          <span style={{ color: 'var(--tm)' }}>{formatDate(source.created_at)}</span>

          {isProcessing && (
            <span style={{ color: 'var(--tm)' }}>Extracting vocabulary candidates…</span>
          )}

          {/* "Nothing to learn" from master — functional addition */}
          {source.status === 'done' && source.candidate_count === 0 && !isProcessing && (
            <span style={{ color: 'var(--td)', fontStyle: 'italic' }}>Nothing to learn</span>
          )}

          {source.candidate_count > 0 && !isProcessing && (
            <>
              {source.status === 'partially_reviewed' && (
                <span style={{ color: 'rgba(249,115,22,.9)', fontWeight: 600 }}>
                  {source.learn_count} / {source.candidate_count} to learn
                </span>
              )}
              {source.status === 'done' && (
                <span style={{ color: 'rgba(16,185,129,.9)', fontWeight: 600 }}>
                  {source.candidate_count} candidates
                </span>
              )}
              {source.status === 'reviewed' && (
                <span style={{ color: 'rgba(148,163,184,.9)', fontWeight: 600 }}>
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
            style={{ background: 'rgba(249,115,22,.12)' }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${reviewProgress}%`,
                background: 'linear-gradient(90deg, rgba(249,115,22,.8), rgba(251,146,60,.5))',
              }}
            />
          </div>
        )}
      </div>

      {/* Right: badge + action button */}
      <div className="flex flex-col items-end gap-2 shrink-0">
        <span
          className="text-[11px] font-semibold px-2.5 py-1 rounded-full whitespace-nowrap"
          style={{ background: badge.bg, color: badge.color }}
        >
          {badge.label}
        </span>

        {(source.status === 'new' || source.status === 'error') && (
          <button
            onClick={() => onProcess(source.id)}
            disabled={isProcessingLocal}
            className="text-xs font-medium rounded-lg disabled:opacity-50 cursor-pointer transition-all hover:brightness-110"
            style={{ ...GHOST_BTN, padding: '5px 11px' }}
          >
            Process →
          </button>
        )}

        {/* done: Review primary + Export secondary (master добавил Export, сохраняем) */}
        {source.status === 'done' && (
          <>
            <button
              onClick={() => onReview(source.id)}
              className="text-xs font-medium rounded-lg cursor-pointer transition-all hover:brightness-110"
              style={{ ...GHOST_BTN, padding: '5px 11px' }}
            >
              Review →
            </button>
            {source.candidate_count > 0 && (
              <button
                onClick={() => onExport(source.id)}
                className="text-xs font-medium rounded-lg cursor-pointer transition-all hover:brightness-110"
                style={{ ...GHOST_BTN, padding: '5px 11px' }}
              >
                Export →
              </button>
            )}
          </>
        )}

        {source.status === 'partially_reviewed' && (
          <button
            onClick={() => onReview(source.id)}
            className="text-xs font-medium rounded-lg cursor-pointer transition-all hover:brightness-110"
            style={{ ...GHOST_BTN, padding: '5px 11px' }}
          >
            Continue →
          </button>
        )}

        {source.status === 'reviewed' && (
          <button
            onClick={() => onExport(source.id)}
            className="text-xs font-medium rounded-lg cursor-pointer transition-all hover:brightness-110"
            style={{ ...GHOST_BTN, padding: '5px 11px' }}
          >
            Export →
          </button>
        )}
      </div>
    </div>
  )
}
