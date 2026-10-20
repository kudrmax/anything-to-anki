import type { StoredCandidate } from '@/api/types'
import { mediaUrl } from './text/meaning'

/** Аудио фразы для пробела и автопроигрывания: из видео, иначе произношение US, иначе TTS. Медиа лежат у источника карточки. */
export function candidateAudioUrl(candidate: StoredCandidate): string | null {
  const sourceId = candidate.source.id
  return mediaUrl(sourceId, candidate.media?.audio_path)
    ?? mediaUrl(sourceId, candidate.pronunciation?.us_audio_path)
    ?? mediaUrl(sourceId, candidate.tts?.audio_path)
}
