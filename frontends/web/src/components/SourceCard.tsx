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
  new:                { label: 'New',       cls: 'bg-slate-800 text-slate-400' },
  processing:         { label: 'Processing',cls: 'bg-indigo-900/60 text-indigo-400' },
  done:               { label: 'Done',      cls: 'bg-emerald-900/60 text-emerald-400' },
  error:              { label: 'Error',     cls: 'bg-rose-900/60 text-rose-400' },
  partially_reviewed: { label: 'In review', cls: 'bg-amber-900/60 text-amber-400' },
  reviewed:           { label: 'Reviewed',  cls: 'bg-sky-900/60 text-sky-400' },
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
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 flex flex-col gap-3 hover:border-slate-700 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-slate-200 leading-relaxed line-clamp-2 flex-1">
          {source.raw_text_preview}
        </p>
        <span className={cn('shrink-0 rounded-md px-2 py-0.5 text-xs font-medium', badge.cls)}>
          {badge.label}
        </span>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{formatDate(source.created_at)}</span>
        {source.candidate_count > 0 && (
          <span className="text-slate-400">{source.candidate_count} candidates</span>
        )}
      </div>

      <div className="flex gap-2">
        {(source.status === 'new' || source.status === 'error') && (
          <button
            onClick={() => onProcess(source.id)}
            disabled={isProcessingLocal}
            className="flex-1 rounded-md border border-indigo-700 px-3 py-1.5 text-xs font-medium text-indigo-400 hover:bg-indigo-950 disabled:opacity-50 transition-colors"
          >
            Process
          </button>
        )}

        {isProcessing && (
          <div className="flex-1 flex items-center justify-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-500">
            <Loader2 size={12} className="animate-spin" />
            Processing…
          </div>
        )}

        {(source.status === 'done' || source.status === 'partially_reviewed') && (
          <>
            <button
              onClick={() => onReview(source.id)}
              className="flex-1 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 transition-colors cursor-pointer"
            >
              {source.status === 'partially_reviewed' ? 'Continue reviewing →' : 'Review →'}
            </button>
            <button
              onClick={() => onExport(source.id)}
              className="rounded-md border border-indigo-700 px-3 py-1.5 text-xs font-medium text-indigo-400 hover:bg-indigo-950 transition-colors cursor-pointer"
            >
              Export →
            </button>
          </>
        )}

        {source.status === 'reviewed' && (
          <button
            onClick={() => onExport(source.id)}
            className="flex-1 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 transition-colors cursor-pointer"
          >
            Export to Anki →
          </button>
        )}
      </div>
    </div>
  )
}
