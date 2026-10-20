import { describe, expect, it, vi } from 'vitest'
import type { GenerationKindStatus, GenerationOverview } from '@/api/types'
import { generationItems } from './generationItems'
import type { Review } from './useReview'

const media = (blocked_by: GenerationKindStatus['blocked_by'], videos_to_download: number): GenerationKindStatus => ({
  kind: 'media', total: 4, done: 1, running: 0, failed: 0, missing: 3, ready_missing: 3, blocked_by, videos_to_download,
})

const itemsOf = (generation: GenerationOverview, downloadVideo = vi.fn()) => {
  const review = { generation, generationActions: { run: vi.fn(), cancel: vi.fn(), downloadVideo } } as unknown as Review
  return generationItems(review)[0].items!
}
const labels = (generation: GenerationOverview) => itemsOf(generation).map(item => item.label)

describe('generationItems', () => {
  it('offers the download of videos a mixed set still lacks, though its media is not held back', () => {
    const downloadVideo = vi.fn()
    const download = itemsOf({ kinds: [media(null, 2)], in_progress: false }, downloadVideo)
      .find(item => item.label === 'Download video')!
    expect(download.value).toBe('2')
    download.onSelect!()
    expect(downloadVideo).toHaveBeenCalledOnce()
  })

  it('offers no download when every video is here or on its way', () => {
    expect(labels({ kinds: [media(null, 0)], in_progress: false })).not.toContain('Download video')
    expect(labels({ kinds: [media('video_downloading', 0)], in_progress: true }))
      .toEqual(expect.arrayContaining(['Downloading video…']))
  })

  it('shows no count for a single video', () => {
    const download = itemsOf({ kinds: [media('video_not_downloaded', 1)], in_progress: false })
      .find(item => item.label === 'Download video')!
    expect(download.value).toBeUndefined()
  })
})
