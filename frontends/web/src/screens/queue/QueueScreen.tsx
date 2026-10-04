import { useEffect, useState, type ReactNode } from 'react'
import { RefreshCw, X } from 'lucide-react'
import { api } from '@/api/client'
import type { FailedGroup, QueueGlobalSummary, QueueJob, SourceSummary } from '@/api/types'
import { useQueuePolling } from '@/hooks/useQueuePolling'
import { Page, PageHeader } from '@/shell'
import { Button, Empty, IconButton, Select, Spinner, Stat, StatGrid, Text } from '@/ui'
import css from './queue.module.css'

const JOB_TYPES: (keyof QueueGlobalSummary)[] = ['polish', 'meaning', 'media', 'pronunciation', 'video_download', 'topic_targets']
const JOB_LABEL: Record<string, string> = {
  polish: 'Polish phrase',
  meaning: 'Meaning',
  media: 'Media',
  pronunciation: 'Pronunciation',
  video_download: 'Video download',
  tts: 'TTS',
  topic_targets: 'Topic targets',
}
const QUEUE_PREVIEW = 20

const jobLabel = (jobType: string): string => JOB_LABEL[jobType] ?? jobType

function JobRow({ job, onDone }: { job: QueueJob; onDone: () => void }) {
  const [cancelling, setCancelling] = useState(false)
  const cancel = async () => {
    setCancelling(true)
    try {
      await api.cancelQueue(job.job_type, undefined, job.job_id)
      onDone()
    } catch {
      // ignore
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className={css.row}>
      <span className={css.type}>{jobLabel(job.job_type)}</span>
      <span className={css.title} title={job.source_title}>{job.source_title}</span>
      <span className={css.detail}>
        {job.status === 'running'
          ? <span className={css.running}><Spinner />Running</span>
          : job.position !== null ? `#${job.position} in line` : 'Queued'}
      </span>
      <IconButton icon={X} label="Cancel" busy={cancelling} onClick={() => void cancel()} />
    </div>
  )
}

function FailedRow({ group, jobType, sourceId, onDone }: { group: FailedGroup; jobType: string; sourceId: number | undefined; onDone: () => void }) {
  const [retrying, setRetrying] = useState(false)
  const retry = async () => {
    setRetrying(true)
    try {
      await api.retryQueue(jobType, sourceId, group.error_text)
      onDone()
    } catch {
      // ignore
    } finally {
      setRetrying(false)
    }
  }
  const sourceNames = group.sources.map(s => `${s.source_title} (${s.count})`).join(', ')

  return (
    <div className={css.row}>
      <span className={css.type}>{jobLabel(jobType)}</span>
      <span className={css.failed}>
        <span className={css.title}>{sourceNames && !sourceId ? sourceNames : jobLabel(jobType)}</span>
        <Text tone="err" size="s">{group.error_text}</Text>
      </span>
      <span className={css.detail}>{group.count} failed</span>
      <IconButton icon={RefreshCw} label={`Retry ${group.count}`} busy={retrying} onClick={() => void retry()} />
    </div>
  )
}

export function QueueScreen() {
  const [sourceId, setSourceId] = useState<number | undefined>(undefined)
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [showAllQueued, setShowAllQueued] = useState(false)
  const { summary, order, failed, loading, refetch } = useQueuePolling(sourceId)

  useEffect(() => {
    api.listSources().then(setSources).catch(() => {})
  }, [])

  const forEachType = async (hasWork: (counts: QueueGlobalSummary[keyof QueueGlobalSummary]) => boolean, run: (jobType: string) => Promise<unknown>) => {
    if (!summary) return
    for (const jobType of JOB_TYPES) {
      if (!hasWork(summary[jobType])) continue
      try {
        await run(jobType)
      } catch {
        // continue with others
      }
    }
    refetch()
  }
  const retryAllFailed = () => forEachType(counts => counts.failed > 0, jobType => api.retryQueue(jobType, sourceId))
  const cancelAllQueued = () => forEachType(counts => counts.queued > 0, jobType => api.cancelQueue(jobType, sourceId))
  const act = async (run: () => Promise<unknown>) => {
    try {
      await run()
    } catch {
      // ignore
    }
    refetch()
  }

  const totalFailed = summary ? JOB_TYPES.reduce((sum, jobType) => sum + summary[jobType].failed, 0) : 0
  const totalRunning = order ? order.running.length : 0
  const totalQueued = order ? order.total_queued : 0
  const isEmpty = !loading && totalFailed === 0 && totalRunning === 0 && totalQueued === 0
  const activeTypes = summary
    ? JOB_TYPES.filter(jobType => summary[jobType].queued > 0 || summary[jobType].running > 0 || summary[jobType].failed > 0)
    : []

  const queuedJobs = order?.queued ?? []
  const visibleQueued = showAllQueued ? queuedJobs : queuedJobs.slice(0, QUEUE_PREVIEW)
  const hiddenCount = queuedJobs.length - visibleQueued.length
  const failedTypes = failed?.types.filter(type => type.total_failed > 0) ?? []

  const header = (
    <PageHeader title="Queue">
      <Select value={sourceId ?? ''} onChange={e => setSourceId(e.target.value ? Number(e.target.value) : undefined)}>
        <option value="">All sources</option>
        {sources.map(source => <option key={source.id} value={source.id}>{source.title}</option>)}
      </Select>
      <Button variant="link" disabled={totalFailed === 0} onClick={() => void retryAllFailed()}>Retry failed</Button>
      <Button variant="danger-link" disabled={totalQueued === 0 && totalRunning === 0} onClick={() => void cancelAllQueued()}>Cancel queued</Button>
    </PageHeader>
  )

  const aside = summary && activeTypes.length > 0 && (
    <StatGrid>
      {activeTypes.map(jobType => {
        const counts = summary[jobType]
        return (
          <Stat
            key={jobType}
            value={counts.running + counts.queued}
            label={`${jobLabel(jobType)} in queue`}
            hint={(counts.failed > 0 || counts.queued > 0) && (
              <span className={css.tileActions}>
                {counts.failed > 0 && <Button variant="link" onClick={() => void act(() => api.retryQueue(jobType, sourceId))}>Retry {counts.failed} failed</Button>}
                {counts.queued > 0 && <Button variant="danger-link" onClick={() => void act(() => api.cancelQueue(jobType, sourceId))}>Cancel {counts.queued}</Button>}
              </span>
            )}
          />
        )
      })}
    </StatGrid>
  )

  const failedRows = failedTypes.flatMap(type => type.groups.map((group, i) => (
    <FailedRow key={`${type.job_type}-${i}`} group={group} jobType={type.job_type} sourceId={sourceId} onDone={refetch} />
  )))
  const groups: { id: string; label: string; count: number; rows: ReactNode }[] = [
    { id: 'running', label: 'Running', count: totalRunning, rows: order?.running.map(job => <JobRow key={job.job_id} job={job} onDone={refetch} />) },
    { id: 'queued', label: 'Queued', count: totalQueued, rows: visibleQueued.map(job => <JobRow key={job.job_id} job={job} onDone={refetch} />) },
    { id: 'failed', label: 'Failed', count: totalFailed, rows: failedRows },
  ]

  return (
    <Page wide header={header} aside={aside || undefined}>
      {loading && <Empty><Spinner /></Empty>}
      {isEmpty && <Empty>{sourceId ? 'This source has no queue activity.' : 'The queue is empty.'}</Empty>}
      {groups.filter(group => group.count > 0).map(group => (
        <section key={group.id} className={css.group}>
          <h2 className={css.groupTitle}>{group.label}<span>{group.count}</span></h2>
          {group.rows}
          {group.id === 'queued' && hiddenCount > 0 && (
            <div className={css.more}><Button variant="link" onClick={() => setShowAllQueued(true)}>Show {hiddenCount} more</Button></div>
          )}
        </section>
      ))}
    </Page>
  )
}
