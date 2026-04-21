import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import { api } from '@/api/client'
import type { ReprocessStats } from '@/api/types'

interface ReprocessModalProps {
  sourceId: number
  onClose: () => void
  onReprocess: () => void
  onOpenExport: (sourceId: number) => void
}

export function ReprocessModal({ sourceId, onClose, onReprocess, onOpenExport }: ReprocessModalProps) {
  const [stats, setStats] = useState<ReprocessStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.getReprocessStats(sourceId)
      .then((s) => { if (!cancelled) setStats(s) })
      .catch((e: Error) => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [sourceId])

  const hasWarning = stats != null && (stats.learn_count > 0 || stats.known_count > 0)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
      }}
      onClick={onClose}
    >
      <div
        className="rounded-2xl p-6 max-w-md w-full flex flex-col gap-4"
        style={{
          background: 'var(--surface-menu)',
          border: '1px solid var(--glass-b)',
          boxShadow: 'var(--sh)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold" style={{ color: 'var(--fg)' }}>
          Reprocess source
        </h3>

        {loading && (
          <p className="text-sm" style={{ color: 'var(--fg-muted)' }}>Loading stats…</p>
        )}

        {error && (
          <p className="text-sm" style={{ color: 'var(--src-error)' }}>
            Failed to load stats: {error}
          </p>
        )}

        {stats != null && (
          <>
            <div className="text-sm flex flex-col gap-1" style={{ color: 'var(--fg-muted)' }}>
              <p className="font-medium" style={{ color: 'var(--fg)' }}>Will be lost:</p>
              <p>{stats.learn_count} learn words</p>
              <p>{stats.known_count} known words</p>
              <p>{stats.skip_count} skip words</p>
            </div>

            {hasWarning && (
              <div
                className="flex items-start gap-2 rounded-lg p-3 text-sm"
                style={{
                  background: 'color-mix(in srgb, var(--src-error) 10%, transparent)',
                  color: 'var(--src-error)',
                }}
              >
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <span>To preserve Learn words, export them to Anki first.</span>
              </div>
            )}

            {stats.has_active_jobs && (
              <div
                className="flex items-start gap-2 rounded-lg p-3 text-sm"
                style={{
                  background: 'color-mix(in srgb, var(--src-processing) 10%, transparent)',
                  color: 'var(--src-processing)',
                }}
              >
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <span>
                  Source has active jobs (meaning/media generation).
                  Cancel them on the source page before reprocessing.
                </span>
              </div>
            )}
          </>
        )}

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="glass-pill text-xs cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={() => onOpenExport(sourceId)}
            className="glass-pill glass-pill-prominent text-xs font-medium cursor-pointer"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            Open export page
          </button>
          <button
            onClick={onReprocess}
            disabled={loading || stats?.has_active_jobs || error != null}
            className="glass-pill text-xs font-medium cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: 'var(--src-error)',
              color: '#fff',
              opacity: (loading || stats?.has_active_jobs || error != null) ? 0.4 : 1,
            }}
          >
            Reprocess source
          </button>
        </div>
      </div>
    </div>
  )
}
