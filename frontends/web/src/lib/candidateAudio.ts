import type { StoredCandidate } from '@/api/types'
import { mediaUrl } from './text/meaning'

/** Аудио карточки для клавиши и автопроигрывания; какое именно, решает backend. Медиа лежат у источника карточки. */
export function candidateAudioUrl(candidate: StoredCandidate): string | null {
  return mediaUrl(candidate.source.id, candidate.audio_path)
}
