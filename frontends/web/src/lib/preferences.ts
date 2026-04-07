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
  default: T
  parse: (raw: string) => T
}

function makePref<T>(spec: PrefSpec<T>): {
  read: () => T
  write: (value: T) => void
} {
  const fullKey = PREFIX + spec.key
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

export const autoPlayAudioPref = makePref<boolean>({
  key: 'review.autoPlayAudio',
  default: true,
  parse: (raw) => raw === 'true',
})
