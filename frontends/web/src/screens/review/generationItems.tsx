import { Download, ListChecks, Plus, RefreshCw, RotateCcw, X } from 'lucide-react'
import type { GenerationKind, GenerationKindStatus } from '@/api/types'
import { Spinner, StatusDot, type MenuItem } from '@/ui'
import type { Review } from './useReview'

const KIND_TEXT: Record<GenerationKind, { label: string; hint: string }> = {
  polish: { label: 'Phrases', hint: 'AI simplifies phrases' },
  meaning: { label: 'Meanings', hint: 'Definition, translation' },
  media: { label: 'Media', hint: 'Screenshot and clip from the video' },
  pronunciation: { label: 'Pronunciation', hint: 'Dictionary recordings' },
  tts: { label: 'Speech', hint: 'Phrase read aloud' },
}

function statusLead(status: GenerationKindStatus) {
  if (status.running > 0 || status.blocked_by === 'video_downloading') return <Spinner />
  if (status.failed > 0) return <StatusDot tone="err" />
  if (status.total > 0 && status.done === status.total) return <StatusDot tone="ok" />
  return <StatusDot />
}

function videoItems(status: GenerationKindStatus, review: Review): MenuItem[] {
  const toDownload = status.videos_to_download
  return [
    ...(status.blocked_by === 'video_downloading'
      ? [{ label: 'Downloading video…', hint: 'Media is cut once it’s here', icon: Download, disabled: true }]
      : []),
    ...(toDownload > 0
      ? [{
          label: 'Download video',
          hint: 'Media is cut from the video file',
          icon: Download,
          value: toDownload > 1 ? String(toDownload) : undefined,
          onSelect: () => void review.generationActions.downloadVideo(),
        }]
      : []),
  ]
}

function kindItems(status: GenerationKindStatus, review: Review): MenuItem[] {
  const { run, cancel } = review.generationActions
  const blocked = status.blocked_by !== null
  const replaceable = status.total - status.running
  return [
    ...videoItems(status, review),
    {
      label: 'Generate for ready phrases',
      hint: 'Missing ones, skipping hidden sections',
      icon: ListChecks,
      value: String(status.ready_missing),
      disabled: blocked || status.ready_missing === 0,
      onSelect: () => void run(status.kind, 'ready_missing'),
    },
    {
      label: 'Generate missing',
      hint: 'Cards that don’t have it yet',
      icon: Plus,
      value: String(status.missing),
      disabled: blocked || status.missing === 0,
      onSelect: () => void run(status.kind, 'missing'),
    },
    {
      label: 'Retry failed',
      hint: 'Cards whose last try failed',
      icon: RotateCcw,
      value: String(status.failed),
      disabled: blocked || status.failed === 0,
      onSelect: () => void run(status.kind, 'failed'),
    },
    {
      label: 'Regenerate all',
      hint: 'Replace it on every card',
      icon: RefreshCw,
      value: String(replaceable),
      disabled: blocked || replaceable === 0,
      separated: true,
      onSelect: () => void run(status.kind, 'all'),
    },
    {
      label: 'Cancel',
      hint: 'Stop queued and running',
      icon: X,
      value: String(status.running),
      danger: true,
      disabled: status.running === 0,
      separated: true,
      onSelect: () => void cancel(status.kind),
    },
  ]
}

/** Пункты генерации по видам: и для своего меню, и для меню «⋯» на телефоне. */
export const generationItems = (review: Review): MenuItem[] =>
  (review.generation?.kinds ?? []).map(status => ({
    label: KIND_TEXT[status.kind].label,
    hint: KIND_TEXT[status.kind].hint,
    lead: statusLead(status),
    value: `${status.done}/${status.total}`,
    items: kindItems(status, review),
  }))
