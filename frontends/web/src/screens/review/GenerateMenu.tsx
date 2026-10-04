import { Download, Plus, RefreshCw, RotateCcw, Sparkles, X } from 'lucide-react'
import type { GenerationKind, GenerationKindStatus } from '@/api/types'
import { Button, Icon, Menu, Spinner, StatusDot, type MenuItem } from '@/ui'
import type { Review } from './useReview'
import css from './review.module.css'

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
  if (status.blocked_by === 'video_downloading') {
    return [{ label: 'Downloading video…', hint: 'Media is cut once it’s here', icon: Download, disabled: true }]
  }
  if (status.blocked_by === 'video_not_downloaded') {
    return [{
      label: 'Download video',
      hint: 'Media is cut from the video file',
      icon: Download,
      onSelect: () => void review.generationActions.downloadVideo(),
    }]
  }
  return []
}

function kindItems(status: GenerationKindStatus, review: Review): MenuItem[] {
  const { run, cancel } = review.generationActions
  const blocked = status.blocked_by !== null
  const replaceable = status.total - status.running
  return [
    ...videoItems(status, review),
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

export function GenerateMenu({ review }: { review: Review }) {
  const { generation } = review
  const items: MenuItem[] = (generation?.kinds ?? []).map(status => ({
    label: KIND_TEXT[status.kind].label,
    hint: KIND_TEXT[status.kind].hint,
    lead: statusLead(status),
    value: `${status.done}/${status.total}`,
    items: kindItems(status, review),
  }))

  return (
    <Menu
      items={items}
      emptyText="Loading…"
      trigger={
        <Button variant="link" className={css.iconTrigger} title="Generate phrases, meanings, audio" aria-label="Generate">
          {generation?.in_progress ? <Spinner /> : <Icon as={Sparkles} />}
        </Button>
      }
    />
  )
}
