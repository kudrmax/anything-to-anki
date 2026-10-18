import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KnownWord, LearningWords } from '@/api/types'
import { KnownWords, LearningWordsList } from './SettingsSections'
import type { SettingsStore } from './useSettings'

const LISTED: KnownWord = { id: 7, lemma: 'run', pos: 'VERB', created_at: '2026-01-01T00:00:00Z', by_timer: false }
const BY_TIMER: KnownWord = { id: null, lemma: 'glare', pos: null, created_at: '2026-10-01T12:00:00Z', by_timer: true }
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

      expect(remove('run · VERB')).not.toBeNull()
      expect(remove('glare · Known: 30 days in Anki')).not.toBeNull()
    })

    it('removes each word as the store is given it, the timer one too', () => {
      const deleteWord = vi.fn()
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER], deleteWord })} />))

      act(() => remove('glare · Known: 30 days in Anki').click())
      act(() => remove('run · VERB').click())

      expect(deleteWord.mock.calls).toEqual([[BY_TIMER], [LISTED]])
    })

    it('holds the word being removed', () => {
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER], deletingKey: 'timer:glare' })} />))

      expect(remove('glare · Known: 30 days in Anki').disabled).toBe(true)
      expect(remove('run · VERB').disabled).toBe(false)
    })
  })

  describe('Learning', () => {
    const render = (learningWords: LearningWords) =>
      act(() => root.render(<LearningWordsList store={store({ learningWords })} />))

    it('shows the day each word in Anki turns Known, and the words waiting for export', () => {
      render({ in_anki: [{ lemma: 'glare', known_on: KNOWN_ON }], awaiting_export: ['drift'] })

      const day = new Date(KNOWN_ON).toLocaleDateString()
      expect(host.textContent).toContain('In Anki · 1')
      expect(host.textContent).toContain(`glare · Known on ${day}`)
      expect(host.textContent).toContain('Waiting for export · 1')
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
