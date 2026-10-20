import { useEffect, useState, type ReactNode } from 'react'
import { ChevronDown, RefreshCw, Trash2, X, type LucideIcon } from 'lucide-react'
import { api } from '@/api/client'
import type { FailedGroup, QueueActionResult, QueueJob, QueueSelection, SourceSummary } from '@/api/types'
import { useQueuePolling } from '@/hooks/useQueuePolling'
import { Page, PageHeader } from '@/shell'
import { Button, Empty, Icon, IconButton, Menu, Spinner, Stat, StatGrid, Text, Toast, useToast } from '@/ui'
import css from './queue.module.css'

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
const QUEUE_ALL = 10000

const jobLabel = (jobType: string): string => JOB_LABEL[jobType] ?? jobType
const plural = (count: number, word: string): string => `${count} ${word}${count === 1 ? '' : 's'}`

type QueueCall = (selection: QueueSelection) => Promise<QueueActionResult>
type RunAction = (call: QueueCall, selection: QueueSelection, done: (affected: number) => string) => Promise<void>

const cancelled = (n: number) => n > 0 ? `Cancelled ${plural(n, 'job')}` : 'Nothing to cancel — it already finished'
const retried = (n: number) => n > 0 ? `Queued ${plural(n, 'job')} again` : 'Nothing to retry'
const dismissed = (n: number) => n > 0 ? `Cleared ${plural(n, 'failure')}` : 'Nothing to clear'

function ActionIcon({ icon, label, onAct }: { icon: LucideIcon; label: string; onAct: () => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const act = async () => {
    setBusy(true)
    try {
      await onAct()
    } finally {
      setBusy(false)
    }
  }
  return <IconButton icon={icon} label={label} busy={busy} onClick={() => void act()} />
}

function JobRow({ job, showSource, run }: { job: QueueJob; showSource: boolean; run: RunAction }) {
  return (
    <div className={css.row}>
      <span className={css.type}>{jobLabel(job.job_type)}</span>
      <span className={css.subject}>
        {job.target !== null && <span className={css.target}>{job.target}</span>}
        {(job.target === null || showSource) && (
          <span className={job.target === null ? css.title : css.source} title={job.source_title}>{job.source_title}</span>
        )}
      </span>
      <span className={css.detail}>
        {job.status === 'running'
          ? <span className={css.running}><Spinner />Running</span>
          : job.position !== null ? `#${job.position} in line` : 'Queued'}
      </span>
      <ActionIcon icon={X} label="Cancel" onAct={() => run(api.cancelQueue, { job_id: job.job_id }, cancelled)} />
    </div>
  )
}

function FailedRow({ group, jobType, sourceId, run }: { group: FailedGroup; jobType: string; sourceId: number | undefined; run: RunAction }) {
  const selection: QueueSelection = { job_type: jobType, source_id: sourceId, error_text: group.error_text }
  const sourceNames = group.sources.map(s => `${s.source_title} (${s.count})`).join(', ')

  return (
    <div className={css.row}>
      <span className={css.type}>{jobLabel(jobType)}</span>
      <span className={css.failed}>
        <span className={css.title}>{sourceNames && sourceId === undefined ? sourceNames : jobLabel(jobType)}</span>
        <Text tone="err" size="s">{group.error_text}</Text>
      </span>
      <span className={css.detail}>{group.count} failed</span>
      <span className={css.actions}>
        <ActionIcon icon={RefreshCw} label={`Retry ${group.count}`} onAct={() => run(api.retryQueue, selection, retried)} />
        <ActionIcon icon={Trash2} label={`Clear ${group.count}`} onAct={() => run(api.dismissQueue, selection, dismissed)} />
      </span>
    </div>
  )
}

export function QueueScreen() {
  const [sourceId, setSourceId] = useState<number | undefined>(undefined)
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [showAllQueued, setShowAllQueued] = useState(false)
  const { queue, loading, refetch } = useQueuePolling(sourceId, showAllQueued ? QUEUE_ALL : QUEUE_PREVIEW)
  const [toast, showToast] = useToast()
  const [toastTone, setToastTone] = useState<'info' | 'warn'>('info')

  useEffect(() => {
    api.listSources().then(setSources).catch(() => {})
  }, [])

  const run: RunAction = async (call, selection, done) => {
    try {
      const { affected } = await call(selection)
      setToastTone('info')
      showToast(done(affected))
    } catch (e) {
      setToastTone('warn')
      showToast(e instanceof Error ? e.message : 'The queue did not respond')
    }
    await refetch()
  }
  const scope: QueueSelection = { source_id: sourceId }

  const totalFailed = queue?.total_failed ?? 0
  const totalRunning = queue?.total_running ?? 0
  const totalQueued = queue?.total_queued ?? 0
  const isEmpty = !loading && totalFailed + totalRunning + totalQueued === 0
  const queuedJobs = queue?.queued ?? []
  const hiddenCount = totalQueued - queuedJobs.length

  const header = (
    <PageHeader title="Queue">
      <Menu
        align="start"
        trigger={
          <Button variant="link" className={css.sourceTrigger}>
            <span className={css.sourceLabel}>{sources.find(source => source.id === sourceId)?.title ?? 'All sources'}</span>
            <Icon as={ChevronDown} size="s" />
          </Button>
        }
        items={[
          { label: 'All sources', selected: sourceId === undefined, onSelect: () => setSourceId(undefined) },
          ...sources.map((source, index) => ({
            label: source.title,
            selected: source.id === sourceId,
            separated: index === 0,
            onSelect: () => setSourceId(source.id),
          })),
        ]}
      />
      <Button variant="link" disabled={totalFailed === 0} onClick={() => void run(api.retryQueue, scope, retried)}>Retry failed</Button>
      <Button variant="link" disabled={totalFailed === 0} onClick={() => void run(api.dismissQueue, scope, dismissed)}>Clear failed</Button>
      <Button variant="danger-link" disabled={totalQueued + totalRunning === 0} onClick={() => void run(api.cancelQueue, scope, cancelled)}>Cancel all</Button>
    </PageHeader>
  )

  const aside = queue && queue.counts.length > 0 && (
    <StatGrid>
      {queue.counts.map(counts => {
        const typeScope: QueueSelection = { ...scope, job_type: counts.job_type }
        const active = counts.queued + counts.running
        return (
          <Stat
            key={counts.job_type}
            value={active}
            label={`${jobLabel(counts.job_type)} in queue`}
            hint={(counts.failed > 0 || active > 0) && (
              <span className={css.tileActions}>
                {counts.failed > 0 && <Button variant="link" onClick={() => void run(api.retryQueue, typeScope, retried)}>Retry {counts.failed} failed</Button>}
                {counts.failed > 0 && <Button variant="link" onClick={() => void run(api.dismissQueue, typeScope, dismissed)}>Clear failed</Button>}
                {active > 0 && <Button variant="danger-link" onClick={() => void run(api.cancelQueue, typeScope, cancelled)}>Cancel {active}</Button>}
              </span>
            )}
          />
        )
      })}
    </StatGrid>
  )

  const failedRows = (queue?.failed ?? []).flatMap(type => type.groups.map(group => (
    <FailedRow key={`${type.job_type}-${group.error_text}`} group={group} jobType={type.job_type} sourceId={sourceId} run={run} />
  )))
  const groups: { id: string; label: string; count: number; rows: ReactNode }[] = [
    { id: 'running', label: 'Running', count: totalRunning, rows: queue?.running.map(job => <JobRow key={job.job_id} job={job} showSource={sourceId === undefined} run={run} />) },
    { id: 'queued', label: 'Queued', count: totalQueued, rows: queuedJobs.map(job => <JobRow key={job.job_id} job={job} showSource={sourceId === undefined} run={run} />) },
    { id: 'failed', label: 'Failed', count: totalFailed, rows: failedRows },
  ]

  return (
    <Page wide header={header} aside={aside || undefined}>
      {loading && !queue && <Empty><Spinner /></Empty>}
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
      <Toast message={toast} tone={toastTone} />
    </Page>
  )
}
