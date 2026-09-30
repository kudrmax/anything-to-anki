/**
 * Client-side user preferences (stored in localStorage).
 *
 * These are pure UI prefs — no backend round-trip. Each preference exposes
 * a `read()` function and a `write()` function. They are typed via a
 * registry below so callers can't accidentally read with the wrong type.
 */

const PREFIX = 'anything-to-anki:'

interface PrefSpec<T> {
  key: string
  /** Ключ хранится без общего префикса — для настроек, записанных до появления реестра. */
  raw?: boolean
  default: T
  parse: (raw: string) => T
}

function makePref<T>(spec: PrefSpec<T>): {
  read: () => T
  write: (value: T) => void
} {
  const fullKey = spec.raw ? spec.key : PREFIX + spec.key
  return {
    read: () => {
      if (typeof window === 'undefined') return spec.default
      try {
        const raw = localStorage.getItem(fullKey)
        if (raw === null) return spec.default
        return spec.parse(raw)
      } catch {
        return spec.default
      }
    },
    write: (value: T) => {
      if (typeof window === 'undefined') return
      try {
        localStorage.setItem(fullKey, String(value))
      } catch {
        // ignore (private mode, quota, etc.)
      }
    },
  }
}

export type ThemeName = 'cosmic' | 'liquid-glass' | 'book'

export const themePref = makePref<ThemeName>({
  key: 'ui.theme',
  default: 'cosmic',
  parse: (raw) => {
    if (raw === 'liquid-glass' || raw === 'book') return raw
    return 'cosmic'
  },
})

export const autoPlayAudioPref = makePref<boolean>({
  key: 'review.autoPlayAudio',
  default: true,
  parse: (raw) => raw === 'true',
})

export type ThemePref = 'light' | 'dark' | 'system'

export const themeModePref = makePref<ThemePref>({
  key: 'ui.themeMode',
  default: 'dark',
  parse: (raw) => (raw === 'light' || raw === 'system' ? raw : 'dark'),
})

export type SortOrder = 'relevance' | 'chronological'

export const sortOrderPref = makePref<SortOrder>({
  key: 'reviewPage.sortOrder',
  raw: true,
  default: 'relevance',
  parse: (raw) => (raw === 'chronological' ? raw : 'relevance'),
})
