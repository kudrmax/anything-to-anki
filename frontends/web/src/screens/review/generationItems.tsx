import { Download, ListStart, Plus, RefreshCw, RotateCcw, X } from 'lucide-react'
import type { GenerationKind, GenerationKindStatus, GenerationScope } from '@/api/types'
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

function kindItems(status: GenerationKindStatus, batchSize: number, review: Review): MenuItem[] {
  const { run, cancel } = review.generationActions
  const blocked = status.blocked_by !== null
  const runItem = (
    scope: GenerationScope, count: number, item: Omit<MenuItem, 'value' | 'disabled' | 'onSelect'>,
  ): MenuItem => ({
    ...item,
    value: String(count),
    disabled: blocked || count === 0,
    onSelect: () => void run(status.kind, scope),
  })
  return [
    ...videoItems(status, review),
    runItem('ready_next', status.ready_next, {
      label: `Ready: generate next ${batchSize}`,
      hint: 'From the top of the list',
      icon: ListStart,
    }),
    runItem('ready_missing', status.ready_missing, {
      label: 'Ready: generate missing',
      hint: 'Ready phrases that don’t have it yet',
      icon: Plus,
    }),
    runItem('ready_all', status.ready_all, {
      label: 'Ready: regenerate all',
      hint: 'Replace it on every Ready phrase',
      icon: RefreshCw,
    }),
    runItem('next', status.next, {
      label: `All: generate next ${batchSize}`,
      hint: 'From the top of the list',
      icon: ListStart,
      separated: true,
    }),
    runItem('missing', status.missing, {
      label: 'All: generate missing',
      hint: 'Cards that don’t have it yet',
      icon: Plus,
    }),
    runItem('all', status.all, {
      label: 'All: regenerate all',
      hint: 'Replace it on every card',
      icon: RefreshCw,
    }),
    runItem('failed', status.failed, {
      label: 'Retry failed',
      hint: 'Cards whose last try failed',
      icon: RotateCcw,
      separated: true,
    }),
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
export const generationItems = (review: Review): MenuItem[] => {
  const generation = review.generation
  if (!generation) return []
  return generation.kinds.map(status => ({
    label: KIND_TEXT[status.kind].label,
    hint: KIND_TEXT[status.kind].hint,
    lead: statusLead(status),
    value: `${status.done}/${status.total}`,
    items: kindItems(status, generation.batch_size, review),
  }))
}
