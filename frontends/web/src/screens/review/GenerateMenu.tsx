import { ChevronDown, Sparkles } from 'lucide-react'
import { Button, Icon, Menu, Spinner, type MenuItem } from '@/ui'
import type { Review } from './useReview'

interface QueueState {
  inflight: number
  failed: number
}

function item(state: QueueState, name: string, generateLabel: string, generate: () => void, cancel: () => void, retry: () => void, disabled = false): MenuItem {
  if (state.inflight > 0) return { label: `Cancel ${name} (${state.inflight})`, onSelect: cancel, danger: true }
  if (state.failed > 0) return { label: `Retry ${name} (${state.failed})`, onSelect: retry }
  return { label: generateLabel, onSelect: generate, disabled }
}

export function GenerateMenu({ review }: { review: Review }) {
  const { queue, batch, source } = review
  const isVideo = source?.content_type === 'video'
  const items: MenuItem[] = [
    item(queue.meaning, 'meanings', 'Generate meanings', () => void batch.generateMeanings(), () => void batch.cancelMeanings(), () => void batch.retryMeanings(), review.busy.generating.size > 0),
  ]
  if (isVideo) {
    if (review.downloadingVideo) items.push({ label: 'Downloading…', onSelect: () => {}, disabled: true })
    else if (queue.media.inflight === 0 && queue.media.failed === 0 && !source?.video_downloaded) items.push({ label: 'Download media', onSelect: () => void batch.downloadVideo() })
    else items.push(item(queue.media, 'media', 'Generate media', () => void batch.generateMedia(), () => void batch.cancelMedia(), () => void batch.retryMedia()))
  }
  items.push(item(queue.pronunciation, 'pronunciation', 'Download pronunciation', () => void batch.downloadPronunciation(), () => void batch.cancelPronunciation(), () => void batch.retryPronunciation()))
  if (!isVideo) {
    items.push(item(queue.tts, 'TTS', 'Generate TTS', () => void batch.generateTTS(), () => void batch.cancelTTS(), () => void batch.retryTTS()))
  }

  return (
    <Menu
      items={items}
      trigger={
        <Button variant="link" title="Meanings · Media · Pronunciation">
          {queue.anyInflight || review.downloadingVideo ? <Spinner /> : <Icon as={Sparkles} size="s" />}
          Generate
          <Icon as={ChevronDown} size="s" />
        </Button>
      }
    />
  )
}
