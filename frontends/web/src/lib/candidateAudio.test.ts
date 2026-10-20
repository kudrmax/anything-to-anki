import { describe, expect, it } from 'vitest'
import type { StoredCandidate } from '@/api/types'
import { candidateAudioUrl } from './candidateAudio'

const candidate = (sourceId: number, audioPath: string | null) =>
  ({ source: { id: sourceId }, audio_path: audioPath }) as unknown as StoredCandidate

describe('candidateAudioUrl', () => {
  it('plays the audio the backend chose, from the card source', () => {
    expect(candidateAudioUrl(candidate(9, 'x/a.mp3'))).toBe('/media/9/a.mp3')
  })
  it('returns null without any audio', () => {
    expect(candidateAudioUrl(candidate(3, null))).toBeNull()
  })
})
