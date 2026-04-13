import { Play, Square } from 'lucide-react'

interface MediaThumbnailProps {
  screenshotUrl?: string | null
  audioUrl?: string | null
  isAudioPlaying: boolean
  onPlayAudio: () => void
  alt?: string
}

export function MediaThumbnail({ screenshotUrl, audioUrl, isAudioPlaying, onPlayAudio, alt = 'Screenshot' }: MediaThumbnailProps) {
  return (
    <div style={{ position: 'relative', width: '160px', height: '90px' }}>
      {screenshotUrl ? (
        <img
          src={screenshotUrl}
          alt={alt}
          width={160}
          height={90}
          style={{
            objectFit: 'cover',
            borderRadius: '8px',
            border: '1px solid var(--glass-b)',
            display: 'block',
          }}
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
        />
      ) : (
        <div style={{
          width: '160px',
          height: '90px',
          borderRadius: '8px',
          border: '1px dashed var(--glass-b)',
          background: 'var(--glass)',
        }} />
      )}
      {audioUrl && (
        <PlayOverlayButton isPlaying={isAudioPlaying} onClick={onPlayAudio} />
      )}
    </div>
  )
}

interface PlayOverlayButtonProps {
  isPlaying: boolean
  onClick: () => void
}

export function PlayOverlayButton({ isPlaying, onClick }: PlayOverlayButtonProps) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      aria-label={isPlaying ? 'Stop audio' : 'Play audio'}
      title={isPlaying ? 'Stop audio' : 'Play audio'}
      className="glass-pill"
      style={{
        position: 'absolute',
        top: '6px',
        right: '6px',
        width: '28px',
        height: '28px',
        padding: '4px',
        justifyContent: 'center',
        border: '1px solid var(--accent)',
        color: 'var(--accent)',
        cursor: 'pointer',
      }}
    >
      {isPlaying ? <Square size={12} fill="currentColor" /> : <Play size={12} fill="currentColor" />}
    </button>
  )
}
