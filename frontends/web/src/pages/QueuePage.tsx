import { useCallback, useEffect, useState } from 'react'
import { Loader2, RefreshCw, X } from 'lucide-react'
import { api } from '@/api/client'
import type { FailedByJobType, FailedGroup, QueueJob, QueueGlobalSummary, SourceSummary } from '@/api/types'
import { useQueuePolling } from '@/hooks/useQueuePolling'

// ─── Job type config ────────────────────────────────────────────────────────

interface JobTypeConfig {
  key: keyof QueueGlobalSummary
  label: string
  color: string
  bg: string
}

const JOB_TYPE_CONFIGS: JobTypeConfig[] = [
  { key: 'youtube_dl',   label: 'YouTube DL',   color: '#a78bfa', bg: 'rgba(167,139,250,.15)' },
  { key: 'processing',   label: 'Processing',   color: '#4ade80', bg: 'rgba(74,222,128,.15)'  },
  { key: 'meanings',     label: 'Meanings',     color: '#fbbf24', bg: 'rgba(251,191,36,.15)'  },
  { key: 'media',        label: 'Media',        color: '#38bdf8', bg: 'rgba(56,189,248,.15)'  },
  { key: 'pronunciation',label: 'Pronunciation',color: '#2dd4bf', bg: 'rgba(45,212,191,.15)'  },
]

function jobTypeColor(jobType: string): { color: string; bg: string } {
  const cfg = JOB_TYPE_CONFIGS.find((c) => c.key === jobType)
  return cfg ? { color: cfg.color, bg: cfg.bg } : { color: 'var(--tm)', bg: 'var(--glass)' }
}

function jobTypeLabel(jobType: string): string {
  const cfg = JOB_TYPE_CONFIGS.find((c) => c.key === jobType)
  return cfg?.label ?? jobType
}

// ─── Job type badge ──────────────────────────────────────────────────────────

function JobTypeBadge({ jobType }: { jobType: string }) {
  const { color, bg } = jobTypeColor(jobType)
  return (
    <span
      className="inline-flex items-center rounded-full text-[10px] font-semibold px-2 py-0.5 shrink-0"
      style={{ color, background: bg, border: `1px solid ${color}33` }}
    >
      {jobTypeLabel(jobType)}
    </span>
  )
}

// ─── Source filter dropdown ──────────────────────────────────────────────────

interface SourceFilterProps {
  sources: SourceSummary[]
  selected: number | undefined
  onChange: (id: number | undefined) => void
}

function SourceFilter({ sources, selected, onChange }: SourceFilterProps) {
  return (
    <select
      value={selected ?? ''}
      onChange={(e) => {
        const val = e.target.value
        onChange(val === '' ? undefined : Number(val))
      }}
      className="rounded-lg px-3 py-1.5 text-xs transition-colors"
      style={{
        background: 'var(--ibg)',
        border: '1.5px solid var(--ib)',
        color: 'var(--text)',
        cursor: 'pointer',
        minWidth: '160px',
      }}
    >
      <option value="">All sources</option>
      {sources.map((s) => (
        <option key={s.id} value={s.id}>
          {s.title}
        </option>
      ))}
    </select>
  )
}

// ─── Counter chip ────────────────────────────────────────────────────────────

function CountChip({
  value,
  label,
  color,
}: {
  value: number
  label: string
  color: string
}) {
  if (value === 0) return null
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full"
      style={{
        background: `${color}18`,
        border: `1px solid ${color}33`,
        color,
      }}
    >
      <span className="font-bold">{value}</span>
      <span style={{ color: `${color}bb` }}>{label}</span>
    </span>
  )
}

// ─── Job type block ──────────────────────────────────────────────────────────

interface JobTypeBlockProps {
  config: JobTypeConfig
  queued: number
  running: number
  failed: number
  sourceId: number | undefined
  onAction: () => void
}

function JobTypeBlock({ config, queued, running, failed, sourceId, onAction }: JobTypeBlockProps) {
  const [loading, setLoading] = useState(false)

  const handleRetry = async () => {
    setLoading(true)
    try {
      await api.retryQueue(config.key, sourceId)
      onAction()
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    setLoading(true)
    try {
      await api.cancelQueue(config.key, sourceId)
      onAction()
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="rounded-xl px-4 py-3 flex flex-col gap-2"
      style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)' }}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-xs font-semibold"
          style={{ color: config.color }}
        >
          {config.label}
        </span>
        <div className="flex items-center gap-1">
          {failed > 0 && (
            <button
              onClick={() => void handleRetry()}
              disabled={loading}
              className="glass-pill text-[10px] cursor-pointer disabled:opacity-50"
              style={{ color: '#f43f5e', padding: '2px 7px' }}
            >
              {loading ? <Loader2 size={10} className="animate-spin" /> : `Retry ${failed}`}
            </button>
          )}
          {queued > 0 && (
            <button
              onClick={() => void handleCancel()}
              disabled={loading}
              className="glass-pill text-[10px] cursor-pointer disabled:opacity-50"
              style={{ color: 'var(--td)', padding: '2px 7px' }}
            >
              {loading ? <Loader2 size={10} className="animate-spin" /> : `Cancel ${queued}`}
            </button>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1.5 flex-wrap">
        <CountChip value={queued}   label="queued"  color="#94a3b8" />
        <CountChip value={running}  label="running" color="#fbbf24" />
        <CountChip value={failed}   label="failed"  color="#f43f5e" />
      </div>
    </div>
  )
}

// ─── Queue job row ───────────────────────────────────────────────────────────

interface QueueJobRowProps {
  job: QueueJob
  onCancel: () => void
}

function QueueJobRow({ job, onCancel }: QueueJobRowProps) {
  const [cancelling, setCancelling] = useState(false)

  const handleCancel = async () => {
    setCancelling(true)
    try {
      await api.cancelQueue(job.job_type, undefined, job.job_id)
      onCancel()
    } catch {
      // ignore
    } finally {
      setCancelling(false)
    }
  }

  const isRunning = job.status === 'running'

  return (
    <div
      className="flex items-center gap-2 rounded-lg px-3 py-2"
      style={{
        background: isRunning ? 'rgba(251,191,36,.06)' : 'var(--glass)',
        border: `1px solid ${isRunning ? 'rgba(251,191,36,.2)' : 'var(--glass-b)'}`,
      }}
    >
      {job.position !== null && (
        <span
          className="text-[10px] font-mono w-5 text-center shrink-0"
          style={{ color: 'var(--td)' }}
        >
          {job.position}
        </span>
      )}
      <JobTypeBadge jobType={job.job_type} />
      <div className="flex-1 min-w-0">
        <span className="text-xs truncate block" style={{ color: 'var(--text)' }}>
          {job.source_title}
        </span>
        {job.substage && (
          <span className="text-[10px]" style={{ color: 'var(--td)' }}>
            {job.substage}
          </span>
        )}
      </div>
      <button
        onClick={() => void handleCancel()}
        disabled={cancelling}
        className="glass-pill cursor-pointer disabled:opacity-50"
        style={{ padding: '2px 6px' }}
        title="Cancel"
      >
        {cancelling
          ? <Loader2 size={10} className="animate-spin" style={{ color: 'var(--td)' }} />
          : <X size={10} style={{ color: 'var(--td)' }} />
        }
      </button>
    </div>
  )
}

// ─── Failed error row ────────────────────────────────────────────────────────

interface FailedErrorRowProps {
  group: FailedGroup
  jobType: string
  sourceId: number | undefined
  onAction: () => void
}

function FailedErrorRow({ group, jobType, sourceId, onAction }: FailedErrorRowProps) {
  const [retrying, setRetrying] = useState(false)

  const handleRetry = async () => {
    setRetrying(true)
    try {
      await api.retryQueue(jobType, sourceId, group.error_text)
      onAction()
    } catch {
      // ignore
    } finally {
      setRetrying(false)
    }
  }

  const sourceNames = group.sources.map((s) => `${s.source_title} (${s.count})`).join(', ')

  return (
    <div
      className="flex items-start gap-2 rounded-lg px-3 py-2.5"
      style={{ background: 'rgba(244,63,94,.05)', border: '1px solid rgba(244,63,94,.12)' }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-xs font-mono truncate" style={{ color: '#f87171' }}>
          {group.error_text}
        </p>
        <p className="text-[10px] mt-0.5" style={{ color: 'var(--td)' }}>
          {group.count} failed
          {sourceNames && !sourceId && ` · ${sourceNames}`}
        </p>
      </div>
      <button
        onClick={() => void handleRetry()}
        disabled={retrying}
        className="glass-pill text-[10px] cursor-pointer disabled:opacity-50 shrink-0"
        style={{ color: '#f43f5e', padding: '2px 8px' }}
      >
        {retrying
          ? <Loader2 size={10} className="animate-spin" />
          : `retry ${group.count}`
        }
      </button>
    </div>
  )
}

// ─── Failed job type group ───────────────────────────────────────────────────

interface FailedJobTypeGroupProps {
  data: FailedByJobType
  sourceId: number | undefined
  onAction: () => void
}

function FailedJobTypeGroup({ data, sourceId, onAction }: FailedJobTypeGroupProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <JobTypeBadge jobType={data.job_type} />
        <span className="text-xs" style={{ color: 'var(--td)' }}>
          {data.total_failed} failed
        </span>
      </div>
      <div className="flex flex-col gap-1.5 ml-1">
        {data.groups.map((g, i) => (
          <FailedErrorRow
            key={i}
            group={g}
            jobType={data.job_type}
            sourceId={sourceId}
            onAction={onAction}
          />
        ))}
      </div>
    </div>
  )
}

// ─── Main QueuePage ──────────────────────────────────────────────────────────

export function QueuePage() {
  const [sourceId, setSourceId] = useState<number | undefined>(undefined)
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [sourcesLoaded, setSourcesLoaded] = useState(false)
  const [showAllQueued, setShowAllQueued] = useState(false)

  // Load sources list for filter dropdown
  const loadSources = useCallback(async () => {
    if (sourcesLoaded) return
    try {
      const list = await api.listSources()
      setSources(list)
      setSourcesLoaded(true)
    } catch {
      // ignore
    }
  }, [sourcesLoaded])

  // Trigger sources load on mount
  useEffect(() => {
    void loadSources()
  }, [loadSources])

  const { summary, order, failed, loading, refetch } = useQueuePolling(sourceId)

  const handleAction = useCallback(() => {
    void refetch()
  }, [refetch])

  const handleRetryAllFailed = async () => {
    if (!summary) return
    for (const cfg of JOB_TYPE_CONFIGS) {
      const counts = summary[cfg.key]
      if (counts.failed > 0) {
        try {
          await api.retryQueue(cfg.key, sourceId)
        } catch {
          // continue with others
        }
      }
    }
    void refetch()
  }

  const handleCancelAllQueued = async () => {
    if (!summary) return
    for (const cfg of JOB_TYPE_CONFIGS) {
      const counts = summary[cfg.key]
      if (counts.queued > 0) {
        try {
          await api.cancelQueue(cfg.key, sourceId)
        } catch {
          // continue with others
        }
      }
    }
    void refetch()
  }

  // Determine empty state
  const totalFailed = summary
    ? JOB_TYPE_CONFIGS.reduce((sum, c) => sum + summary[c.key].failed, 0)
    : 0
  const totalRunning = order ? order.running.length : 0
  const totalQueued = order ? order.total_queued : 0
  const isEmpty = !loading && totalFailed === 0 && totalRunning === 0 && totalQueued === 0

  // Active job type blocks (non-zero)
  const activeBlocks = summary
    ? JOB_TYPE_CONFIGS.filter((c) => {
        const s = summary[c.key]
        return s.queued > 0 || s.running > 0 || s.failed > 0
      })
    : []

  // Total failed for global retry button
  const hasFailed = totalFailed > 0
  const hasQueued = totalQueued > 0 || totalRunning > 0

  // Queue order display
  const QUEUE_PREVIEW = 20
  const queuedJobs = order?.queued ?? []
  const visibleQueued = showAllQueued ? queuedJobs : queuedJobs.slice(0, QUEUE_PREVIEW)
  const hiddenCount = queuedJobs.length - visibleQueued.length

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <main className="mx-auto max-w-3xl px-4 py-8 flex flex-col gap-6">

        {/* Zone 1: Header — filter + global actions */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <h2
              className="text-sm font-medium uppercase tracking-wider"
              style={{ color: 'var(--tm)' }}
            >
              Queue
            </h2>
            <SourceFilter
              sources={sources}
              selected={sourceId}
              onChange={setSourceId}
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => void handleRetryAllFailed()}
              disabled={!hasFailed}
              className="glass-pill text-xs cursor-pointer disabled:opacity-30"
              style={{ color: '#f43f5e', gap: '5px' }}
            >
              <RefreshCw size={11} />
              Retry All Failed
            </button>
            <button
              onClick={() => void handleCancelAllQueued()}
              disabled={!hasQueued}
              className="glass-pill text-xs cursor-pointer disabled:opacity-30"
              style={{ color: 'var(--td)', gap: '5px' }}
            >
              <X size={11} />
              Cancel All Queued
            </button>
          </div>
        </div>

        {/* Empty state */}
        {isEmpty && (
          <div
            className="rounded-xl border border-dashed p-10 text-center"
            style={{ borderColor: 'var(--glass-b)' }}
          >
            <p className="text-sm" style={{ color: 'var(--td)' }}>
              {sourceId != null
                ? 'У этого источника нет активности в очереди'
                : 'Очередь пуста'}
            </p>
          </div>
        )}

        {/* Zone 2: Job type blocks */}
        {activeBlocks.length > 0 && summary && (
          <section className="flex flex-col gap-2">
            <h3
              className="text-[11px] font-medium uppercase tracking-wider"
              style={{ color: 'var(--td)' }}
            >
              Job Types
            </h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {activeBlocks.map((cfg) => {
                const counts = summary[cfg.key]
                return (
                  <JobTypeBlock
                    key={cfg.key}
                    config={cfg}
                    queued={counts.queued}
                    running={counts.running}
                    failed={counts.failed}
                    sourceId={sourceId}
                    onAction={handleAction}
                  />
                )
              })}
            </div>
          </section>
        )}

        {/* Zone 3: Queue Order */}
        {order && (totalRunning > 0 || totalQueued > 0) && (
          <section className="flex flex-col gap-3">
            <h3
              className="text-[11px] font-medium uppercase tracking-wider"
              style={{ color: 'var(--td)' }}
            >
              Queue Order
            </h3>

            {/* Running */}
            {order.running.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <div
                  className="text-[10px] font-semibold uppercase tracking-wider"
                  style={{ color: '#fbbf24' }}
                >
                  Running ({order.running.length})
                </div>
                {order.running.map((job) => (
                  <QueueJobRow key={job.job_id} job={job} onCancel={handleAction} />
                ))}
              </div>
            )}

            {/* Queued */}
            {queuedJobs.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <div
                  className="text-[10px] font-semibold uppercase tracking-wider"
                  style={{ color: 'var(--tm)' }}
                >
                  Queued ({order.total_queued})
                </div>
                {visibleQueued.map((job) => (
                  <QueueJobRow key={job.job_id} job={job} onCancel={handleAction} />
                ))}
                {hiddenCount > 0 && (
                  <button
                    onClick={() => setShowAllQueued(true)}
                    className="text-xs text-left cursor-pointer hover:brightness-125 transition-all"
                    style={{ color: 'var(--tm)' }}
                  >
                    ... ещё {hiddenCount} jobs
                  </button>
                )}
              </div>
            )}
          </section>
        )}

        {/* Zone 4: Failed section */}
        {failed && failed.types.length > 0 && (
          <section className="flex flex-col gap-3">
            <h3
              className="text-[11px] font-medium uppercase tracking-wider"
              style={{ color: 'var(--td)' }}
            >
              Failed
            </h3>
            <div className="flex flex-col gap-4">
              {failed.types.map((typeData) => (
                <FailedJobTypeGroup
                  key={typeData.job_type}
                  data={typeData}
                  sourceId={sourceId}
                  onAction={handleAction}
                />
              ))}
            </div>
          </section>
        )}

      </main>
    </div>
  )
}
