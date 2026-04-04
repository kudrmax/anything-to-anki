import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SourceStatus, SourceSummary } from '@/api/types'

interface SourceCardProps {
  source: SourceSummary
  onProcess: (id: number) => void
  onReview: (id: number) => void
  onExport: (id: number) => void
  isProcessingLocal: boolean
}

const STATUS_BADGE: Record<SourceStatus, { label: string; cls: string }> = {
  new:                { label: 'New',        cls: 'bg-slate-800/60 text-slate-400' },
  processing:         { label: 'Processing', cls: 'bg-indigo-900/40 text-indigo-300' },
  done:               { label: 'Done',       cls: 'bg-emerald-900/40 text-emerald-300' },
  error:              { label: 'Error',      cls: 'bg-rose-900/40 text-rose-300' },
  partially_reviewed: { label: 'In review',  cls: 'bg-amber-900/40 text-amber-300' },
  reviewed:           { label: 'Reviewed',   cls: 'bg-sky-900/40 text-sky-300' },
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

export function SourceCard({ source, onProcess, onReview, onExport, isProcessingLocal }: SourceCardProps) {
  const badge = STATUS_BADGE[source.status]
  const isProcessing = source.status === 'processing' || isProcessingLocal

  return (
    <div className="glass-card rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm leading-relaxed line-clamp-2 flex-1" style={{ color: 'var(--text)' }}>
          {source.raw_text_preview}
        </p>
        <span className={cn('shrink-0 rounded-md px-2 py-0.5 text-xs font-medium', badge.cls)}>
          {badge.label}
        </span>
      </div>

      <div className="flex items-center justify-between text-xs" style={{ color: 'var(--td)' }}>
        <span>{formatDate(source.created_at)}</span>
        {source.candidate_count > 0 && (
          <span style={{ color: 'var(--tm)' }}>
            {source.candidate_count} candidates
            {source.learn_count > 0 && (
              <> · <span style={{ color: 'var(--accent)' }}>{source.learn_count} to learn</span></>
            )}
          </span>
        )}
      </div>

      <div className="flex gap-2">
        {(source.status === 'new' || source.status === 'error') && (
          <button
            onClick={() => onProcess(source.id)}
            disabled={isProcessingLocal}
            className="flex-1 rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
            style={{ border: '1px solid var(--ag)', color: 'var(--accent)', background: 'var(--abg)' }}
          >
            Process
          </button>
        )}

        {isProcessing && (
          <div className="flex-1 flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs"
            style={{ border: '1px solid var(--glass-b)', color: 'var(--td)' }}>
            <Loader2 size={12} className="animate-spin" />
            Processing…
          </div>
        )}

        {(source.status === 'done' || source.status === 'partially_reviewed') && (
          <>
            <button
              onClick={() => onReview(source.id)}
              className="flex-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white transition-all hover:brightness-110 cursor-pointer"
              style={{ background: 'var(--accent)' }}
            >
              {source.status === 'partially_reviewed' ? 'Continue reviewing →' : 'Review →'}
            </button>
            <button
              onClick={() => onExport(source.id)}
              className="rounded-lg px-3 py-1.5 text-xs font-medium transition-all hover:brightness-110 cursor-pointer"
              style={{ border: '1px solid var(--ag)', color: 'var(--accent)', background: 'var(--abg)' }}
            >
              Export →
            </button>
          </>
        )}

        {source.status === 'reviewed' && (
          <button
            onClick={() => onExport(source.id)}
            className="flex-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white transition-all hover:brightness-110 cursor-pointer"
            style={{ background: 'var(--accent)' }}
          >
            Export to Anki →
          </button>
        )}
      </div>
    </div>
  )
}
