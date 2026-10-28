import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KnownWord, LearningWords } from '@/api/types'
import { KnownWords, LearningWordsList } from './WordLists'
import type { SettingsStore } from '../useSettings'

const LISTED: KnownWord = {
  id: 7, lemma: 'run', pos: 'VERB', created_at: '2026-01-01T00:00:00Z', removal_key: 'entry:7', by_timer: false,
}
const BY_TIMER: KnownWord = {
  id: null, lemma: 'glare', pos: null, created_at: '2026-10-01T12:00:00Z', removal_key: 'timer:glare', by_timer: true,
}
const KNOWN_ON = '2026-11-17T12:00:00Z'

describe('Settings word lists', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const store = (changes: Partial<SettingsStore>): SettingsStore => ({
    knownWords: [], learningWords: { in_anki: [], awaiting_export: [] }, deletingKey: null, deleteWord: vi.fn(),
    ...changes,
  }) as unknown as SettingsStore
  const remove = (label: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="Remove ${label}"]`)!

  describe('Known words', () => {
    it('marks a word known by its 30 days in Anki', () => {
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER] })} />))

      expect(remove('run verb')).not.toBeNull()
      expect(remove('glare 30 days in Anki')).not.toBeNull()
    })

    it('removes each word as the store is given it, the timer one too', () => {
      const deleteWord = vi.fn()
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER], deleteWord })} />))

      act(() => remove('glare 30 days in Anki').click())
      act(() => remove('run verb').click())

      expect(deleteWord.mock.calls).toEqual([[BY_TIMER], [LISTED]])
    })

    it('shows why a word could not be removed', () => {
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED], knownError: '409: busy' })} />))

      expect(host.textContent).toContain('409: busy')
    })

    it('holds the word being removed', () => {
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER], deletingKey: 'timer:glare' })} />))

      expect(remove('glare 30 days in Anki').disabled).toBe(true)
      expect(remove('run verb').disabled).toBe(false)
    })
  })

  describe('Learning', () => {
    const render = (learningWords: LearningWords) =>
      act(() => root.render(<LearningWordsList store={store({ learningWords })} />))

    it('shows the day each word in Anki turns Known, and the words waiting for export', () => {
      render({ in_anki: [{ lemma: 'glare', known_on: KNOWN_ON }], awaiting_export: ['drift'] })

      const day = new Date(KNOWN_ON).toLocaleDateString()
      expect(host.textContent).toContain('In Anki')
      expect(host.textContent).toContain(`glareknown on ${day}`)
      expect(host.textContent).toContain('Waiting for export')
      expect(host.textContent).toContain('drift')
    })

    it('leaves out an empty group', () => {
      render({ in_anki: [], awaiting_export: ['drift'] })

      expect(host.textContent).not.toContain('In Anki')
    })

    it('says when there is nothing to learn', () => {
      render({ in_anki: [], awaiting_export: [] })

      expect(host.textContent).toContain('Nothing to learn yet')
    })
  })
})
