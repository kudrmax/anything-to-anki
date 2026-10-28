import type { ReactNode } from 'react'
import type { StoredCandidate } from '@/api/types'

export interface CardMedia {
  screenshotUrl: string | null
  audioUrl: string | null
  meaningImageUrl: string | null
}

/** Всё, что нужно блокам тела карточки: сама карточка и то, что делают её кнопки. */
export interface CardBlockContext {
  candidate: StoredCandidate
  media: CardMedia
  playingUrl: string | null
  togglePlay: (url: string) => void
  /** Аудио, которое играет клавиша: она подписана на его кнопке. */
  keyAudioUrl: string | null
  generating: boolean
  generate: () => void
  useExample: (line: string) => void
  /** Подсказки картинок, пока у карточки нет своей; null — подсказки выключены. */
  pictureSuggestions: ReactNode
  showCefr: (anchor: HTMLElement | null) => void
}
