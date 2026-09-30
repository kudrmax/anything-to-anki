import { useCallback, useEffect, useRef, useState } from 'react'

/** Один плеер на экран: одновременно играет не больше одного аудио. */
export function useAudioPlayer() {
  const [playingUrl, setPlayingUrl] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current = null
    }
    setPlayingUrl(null)
  }, [])

  const play = useCallback((url: string) => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    const audio = new Audio(url)
    audioRef.current = audio
    const clear = () => {
      if (audioRef.current === audio) {
        audioRef.current = null
        setPlayingUrl(null)
      }
    }
    audio.addEventListener('ended', clear)
    audio.addEventListener('error', clear)
    audio.play().then(() => setPlayingUrl(url)).catch(() => clear())
  }, [])

  const toggle = useCallback((url: string) => {
    if (playingUrl === url) stop()
    else play(url)
  }, [playingUrl, play, stop])

  useEffect(() => () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
  }, [])

  return { playingUrl, play, stop, toggle }
}

export type AudioPlayer = ReturnType<typeof useAudioPlayer>
