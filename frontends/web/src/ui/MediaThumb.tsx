import { CirclePlay, CircleStop } from 'lucide-react'
import type { EnrichmentStatus } from '@/api/types'
import { Icon } from './Icon'
import css from './MediaThumb.module.css'

interface MediaThumbProps {
  screenshotUrl: string | null
  audioUrl: string | null
  status?: EnrichmentStatus
  error?: string | null
  playing: boolean
  onToggle: (url: string) => void
}

const PLACEHOLDER: Partial<Record<EnrichmentStatus, string>> = { running: 'Generating', queued: 'Queued', failed: 'Failed' }

export function MediaThumb({ screenshotUrl, audioUrl, status, error, playing, onToggle }: MediaThumbProps) {
  const placeholder = status ? PLACEHOLDER[status] : undefined
  if (!screenshotUrl && !audioUrl && !placeholder) return null
  return (
    <div className={css.thumb} title={error ?? undefined}>
      {screenshotUrl && <img className={css.thumbImage} src={screenshotUrl} alt="" onError={e => { e.currentTarget.hidden = true }} />}
      {audioUrl ? (
        <button type="button" className={css.play} aria-label={playing ? 'Stop' : 'Play'} onClick={() => onToggle(audioUrl)}>
          <Icon as={playing ? CircleStop : CirclePlay} />
        </button>
      ) : !screenshotUrl && placeholder}
    </div>
  )
}
