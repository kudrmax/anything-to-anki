import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KnownWord, LearningWords as LearningList } from '@/api/types'
import { KnownWords, LearningWords } from './MyWords'
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
    it('says how each word became known', () => {
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER] })} />))

      const rows = [...host.querySelectorAll('tbody tr')].map(row => [...row.querySelectorAll('td')].map(cell => cell.textContent))
      expect(rows.map(row => [row[0], row[1]])).toEqual([['run', 'verb'], ['glare', '']])
      expect(rows[0][2]).not.toContain('Anki')
      expect(rows[1][2]).toContain('after 30 days in Anki')
    })

    it('removes each word as the store is given it, the timer one too', () => {
      const deleteWord = vi.fn()
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER], deleteWord })} />))

      act(() => remove('glare').click())
      act(() => remove('run').click())

      expect(deleteWord.mock.calls).toEqual([[BY_TIMER], [LISTED]])
    })

    it('shows why a word could not be removed', () => {
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED], knownError: '409: busy' })} />))

      expect(host.textContent).toContain('409: busy')
    })

    it('holds the word being removed', () => {
      act(() => root.render(<KnownWords store={store({ knownWords: [LISTED, BY_TIMER], deletingKey: 'timer:glare' })} />))

      expect(remove('glare').disabled).toBe(true)
      expect(remove('run').disabled).toBe(false)
    })
  })

  describe('Learning', () => {
    const render = (learningWords: LearningList) =>
      act(() => root.render(<LearningWords store={store({ learningWords })} />))

    it('shows the day each word in Anki turns Known, and the words waiting for export', () => {
      render({ in_anki: [{ lemma: 'glare', known_on: KNOWN_ON }], awaiting_export: ['drift'] })

      const day = new Date(KNOWN_ON).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
      const rows = [...host.querySelectorAll('tbody tr')].map(row => [...row.querySelectorAll('td')].map(cell => cell.textContent))
      expect(rows).toEqual([['drift', 'Waiting for export', ''], ['glare', 'In Anki', day]])
    })

    it('says when there is nothing to learn', () => {
      render({ in_anki: [], awaiting_export: [] })

      expect(host.textContent).toContain('Nothing to learn yet')
    })
  })
})

describe('Word table', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const word = (n: number): KnownWord => ({
    id: n, lemma: `word${n}`, pos: null, created_at: '2026-01-01T00:00:00Z', removal_key: `entry:${n}`, by_timer: false,
  })
  const many = Array.from({ length: 120 }, (_, n) => word(n))
  const words = () => [...host.querySelectorAll('tbody tr td:first-child')].map(cell => cell.textContent)
  const render = () => act(() => root.render(<KnownWords store={{ knownWords: many, deletingKey: null, deleteWord: vi.fn() } as unknown as SettingsStore} />))

  it('shows a page at a time and the next page on request', () => {
    render()
    expect(words()).toHaveLength(50)

    act(() => [...host.querySelectorAll('button')].find(b => b.textContent === 'Show 50 more')!.click())

    expect(words()).toHaveLength(100)
  })

  it('finds a word among all of them, not only the shown page', () => {
    render()
    const search = host.querySelector('input')!
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!

    act(() => {
      setValue.call(search, 'word119')
      search.dispatchEvent(new Event('input', { bubbles: true }))
    })

    expect(words()).toEqual(['word119'])
  })
})
