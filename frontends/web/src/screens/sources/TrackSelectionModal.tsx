import { useState } from 'react'
import type { AudioTrack, SubtitleTrack } from '@/api/types'
import { Button, Chip, Label, Modal, Stack } from '@/ui'

interface TrackSelectionModalProps {
  subtitleTracks: SubtitleTrack[]
  audioTracks: AudioTrack[]
  onCancel: () => void
  onConfirm: (subtitleIndex: number | undefined, audioIndex: number | undefined) => void
}

const trackLabel = (track: SubtitleTrack | AudioTrack): string =>
  `${track.title ?? track.language ?? `Track ${track.index}`} — ${track.language ?? '—'} · ${track.codec}`

export function TrackSelectionModal({ subtitleTracks, audioTracks, onCancel, onConfirm }: TrackSelectionModalProps) {
  const [subtitleIndex, setSubtitleIndex] = useState<number | null>(subtitleTracks[0]?.index ?? null)
  const [audioIndex, setAudioIndex] = useState<number | null>(audioTracks[0]?.index ?? null)

  return (
    <Modal
      title="Choose tracks"
      onClose={onCancel}
      footer={
        <>
          <Button variant="link" onClick={onCancel}>Cancel</Button>
          <Button variant="fill" onClick={() => onConfirm(subtitleIndex ?? undefined, audioIndex ?? undefined)}>Confirm</Button>
        </>
      }
    >
      {subtitleTracks.length > 0 && (
        <div>
          <Label flush>Subtitle track</Label>
          <Stack>
            {subtitleTracks.map(track => (
              <Chip key={track.index} outlined on={subtitleIndex === track.index} onClick={() => setSubtitleIndex(track.index)}>
                {trackLabel(track)}
              </Chip>
            ))}
          </Stack>
        </div>
      )}
      {audioTracks.length > 0 && (
        <div>
          <Label flush>Audio track</Label>
          <Stack>
            {audioTracks.map(track => (
              <Chip key={track.index} outlined on={audioIndex === track.index} onClick={() => setAudioIndex(track.index)}>
                {trackLabel(track)}
              </Chip>
            ))}
          </Stack>
        </div>
      )}
    </Modal>
  )
}
