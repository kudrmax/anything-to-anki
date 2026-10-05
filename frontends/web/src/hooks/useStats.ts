import { useSyncExternalStore } from 'react'
import { api } from '@/api/client'
import type { Stats } from '@/api/types'

const POLL_INTERVAL_MS = 3000

const listeners = new Set<() => void>()
let current: Stats | null = null
let timer: ReturnType<typeof setInterval> | null = null

async function refresh(): Promise<void> {
  try {
    current = await api.getStats()
    listeners.forEach(listener => listener())
  } catch {
    // a missed poll is retried on the next tick
  }
}

function startPolling(): void {
  if (timer === null) timer = setInterval(() => void refresh(), POLL_INTERVAL_MS)
}

function stopPolling(): void {
  if (timer !== null) clearInterval(timer)
  timer = null
}

function onVisibility(): void {
  if (document.hidden) {
    stopPolling()
  } else {
    void refresh()
    startPolling()
  }
}

/** Одно хранилище на всё приложение: счётчики видят и навигация, и экраны, которые их меняют. */
export const statsStore = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener)
    if (listeners.size === 1) {
      document.addEventListener('visibilitychange', onVisibility)
      onVisibility()
    }
    return () => {
      listeners.delete(listener)
      if (listeners.size === 0) {
        document.removeEventListener('visibilitychange', onVisibility)
        stopPolling()
      }
    }
  },
  getSnapshot: (): Stats | null => current,
  refresh,
}

export function useStats(): Stats | null {
  return useSyncExternalStore(statsStore.subscribe, statsStore.getSnapshot)
}
