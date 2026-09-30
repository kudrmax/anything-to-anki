import { describe, expect, it } from 'vitest'
import type { StoredCandidate } from '@/api/types'
import { candidateAudioUrl } from './candidateAudio'

const candidate = (paths: { media?: string; us?: string; tts?: string }) => ({
  media: paths.media ? { audio_path: paths.media } : null,
  pronunciation: paths.us ? { us_audio_path: paths.us } : null,
  tts: paths.tts ? { audio_path: paths.tts } : null,
}) as unknown as StoredCandidate

describe('candidateAudioUrl', () => {
  it('prefers the audio from the source video', () => {
    expect(candidateAudioUrl(candidate({ media: '/m/1_audio.mp3', us: '/m/us.mp3', tts: '/m/tts.mp3' }), 3)).toBe('/media/3/1_audio.mp3')
  })
  it('falls back to the US pronunciation', () => {
    expect(candidateAudioUrl(candidate({ us: '/m/us.mp3', tts: '/m/tts.mp3' }), 3)).toBe('/media/3/us.mp3')
  })
  it('falls back to TTS when nothing else exists', () => {
    expect(candidateAudioUrl(candidate({ tts: '/m/tts.mp3' }), 3)).toBe('/media/3/tts.mp3')
  })
  it('returns null without any audio', () => {
    expect(candidateAudioUrl(candidate({}), 3)).toBeNull()
  })
})
