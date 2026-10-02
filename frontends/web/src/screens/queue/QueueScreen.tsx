import { useEffect, useState } from 'react'
import { RefreshCw, X } from 'lucide-react'
import { api } from '@/api/client'
import type { FailedGroup, QueueGlobalSummary, QueueJob, SourceSummary } from '@/api/types'
import { useQueuePolling } from '@/hooks/useQueuePolling'
import { Aside, Page, PageHeader } from '@/shell'
import { Button, DividerRow, Empty, IconButton, Row, Select, Spinner, Stack, Text } from '@/ui'

const JOB_TYPES: (keyof QueueGlobalSummary)[] = ['meaning', 'media', 'pronunciation', 'video_download', 'topic_targets']
const JOB_LABEL: Record<string, string> = {
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
  const details = [
    jobLabel(job.job_type),
    job.candidate_id != null ? `candidate #${job.candidate_id}` : null,
    job.position !== null ? `position ${job.position}` : null,
  ].filter(Boolean).join(' · ')

  return (
    <Row
      tone={job.status === 'running' ? 'run' : 'idle'}
      title={job.source_title}
      meta={details}
      trailing={
        <>
          {job.status === 'running' ? 'Running' : 'Queued'}
          <IconButton icon={X} label="Cancel" busy={cancelling} onClick={() => void cancel()} />
        </>
      }
    />
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
    <Row
      tone="err"
      title={sourceNames && !sourceId ? sourceNames : jobLabel(jobType)}
      meta={<Text tone="err">{jobLabel(jobType)} · {group.count} failed · {group.error_text}</Text>}
      trailing={
        <>
          Failed
          <IconButton icon={RefreshCw} label={`Retry ${group.count}`} busy={retrying} onClick={() => void retry()} />
        </>
      }
    />
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
    <Aside title="By type">
      {activeTypes.map((jobType, i) => {
        const counts = summary[jobType]
        const parts = [
          counts.running > 0 ? `${counts.running} running` : null,
          counts.queued > 0 ? `${counts.queued} queued` : null,
          counts.failed > 0 ? `${counts.failed} failed` : null,
        ].filter(Boolean).join(' · ')
        return (
          <DividerRow
            key={jobType}
            compact
            last={i === activeTypes.length - 1}
            label={jobLabel(jobType)}
            hint={(counts.failed > 0 || counts.queued > 0) && (
              <Stack row gap="m">
                {counts.failed > 0 && <Button variant="link" onClick={() => void act(() => api.retryQueue(jobType, sourceId))}>Retry {counts.failed}</Button>}
                {counts.queued > 0 && <Button variant="danger-link" onClick={() => void act(() => api.cancelQueue(jobType, sourceId))}>Cancel {counts.queued}</Button>}
              </Stack>
            )}
          >
            <Text tone="muted" size="s">{parts}</Text>
          </DividerRow>
        )
      })}
    </Aside>
  )

  return (
    <Page header={header} aside={aside || undefined}>
      {loading && <Empty><Spinner /></Empty>}
      {isEmpty && <Empty>{sourceId ? 'This source has no queue activity.' : 'The queue is empty.'}</Empty>}
      {order?.running.map(job => <JobRow key={job.job_id} job={job} onDone={refetch} />)}
      {visibleQueued.map(job => <JobRow key={job.job_id} job={job} onDone={refetch} />)}
      {hiddenCount > 0 && <Empty><Button variant="link" onClick={() => setShowAllQueued(true)}>Show {hiddenCount} more</Button></Empty>}
      {failedTypes.flatMap(type => type.groups.map((group, i) => (
        <FailedRow key={`${type.job_type}-${i}`} group={group} jobType={type.job_type} sourceId={sourceId} onDone={refetch} />
      )))}
    </Page>
  )
}
