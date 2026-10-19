import { act, useEffect } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KnownWord } from '@/api/types'
import { useSettings, type SettingsStore } from './useSettings'

const { api } = vi.hoisted(() => ({
  api: {
    deleteKnownWord: vi.fn(),
    getKnownWords: vi.fn(),
    getLearningWords: vi.fn(),
  } as Record<string, ReturnType<typeof vi.fn>>,
}))

// Every call the screen makes on mount resolves to nothing; the tests set the ones they need.
vi.mock('@/api/client', () => ({
  api: new Proxy(api, { get: (target, name: string) => target[name] ?? (() => Promise.resolve([])) }),
}))

const LISTED: KnownWord = {
  id: 7, lemma: 'run', pos: 'VERB', created_at: '2026-01-01T00:00:00Z', removal_key: 'entry:7', by_timer: false,
}
const BY_TIMER: KnownWord = {
  id: null, lemma: 'glare', pos: null, created_at: '2026-10-01T12:00:00Z', removal_key: 'timer:glare', by_timer: true,
}

describe('useSettings removal of a known word', () => {
  let host: HTMLDivElement
  let root: Root
  const latest: { store: SettingsStore | null } = { store: null }
  const store = () => latest.store!

  function Probe() {
    const current = useSettings()
    useEffect(() => {
      latest.store = current
    })
    return null
  }

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    Object.values(api).forEach(fn => fn.mockReset())
    host = document.createElement('div')
    root = createRoot(host)
    await act(async () => root.render(<Probe />))
  })

  afterEach(() => act(() => root.unmount()))

  it.each([['a listed word', LISTED], ['a word known by its timer', BY_TIMER]])(
    'removes %s by the key the backend gave it',
    async (_name, word) => {
      api.deleteKnownWord.mockResolvedValue({})
      api.getKnownWords.mockResolvedValue([])
      api.getLearningWords.mockResolvedValue({ in_anki: [], awaiting_export: [] })

      await act(async () => store().deleteWord(word))

      expect(api.deleteKnownWord).toHaveBeenCalledWith(word.removal_key)
    },
  )

  it.each([['a listed word', LISTED], ['a word known by its timer', BY_TIMER]])(
    'shows the refusal of a removal of %s and frees the word',
    async (_name, word) => {
      api.deleteKnownWord.mockRejectedValue(new Error('409: busy'))

      await act(async () => store().deleteWord(word))

      expect(store().knownError).toBe('409: busy')
      expect(store().deletingKey).toBeNull()
    },
  )

  it('clears the refusal at the next removal', async () => {
    api.deleteKnownWord.mockRejectedValueOnce(new Error('409: busy')).mockResolvedValue({})
    api.getKnownWords.mockResolvedValue([])
    api.getLearningWords.mockResolvedValue({ in_anki: [], awaiting_export: [] })

    await act(async () => store().deleteWord(LISTED))
    await act(async () => store().deleteWord(LISTED))

    expect(store().knownError).toBeNull()
  })
})
