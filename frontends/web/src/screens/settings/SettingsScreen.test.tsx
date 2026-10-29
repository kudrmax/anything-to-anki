import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SettingsScreen } from './SettingsScreen'
import type { SettingsStore } from './useSettings'

const STORE = {
  loading: false, form: { usage_group_order: [] }, saveError: null, saving: false, saved: false,
  knownWords: [], unknownWords: [], learningWords: { in_anki: [], awaiting_export: [] }, deletingKey: null,
  frequentWordThresholds: [], bootstrapStatus: null, confirming: null, savedAt: null, noteTypes: [], noteTypesError: null, mediaStats: [], mediaStatsLoading: false,
} as unknown as SettingsStore

vi.mock('./useSettings', () => ({ useSettings: () => STORE, unknownWordKey: (id: number) => `unknown:${id}` }))
vi.mock('./UpdatesSection', () => ({ Updates: () => null }))

describe('Settings sections', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const open = (search: string) =>
    act(() => root.render(<MemoryRouter initialEntries={[`/settings${search}`]}><SettingsScreen /></MemoryRouter>))
  const current = () => host.querySelector('nav [aria-current="page"]')?.textContent
  const tab = () => host.querySelector('[role="tab"][aria-selected="true"]')?.textContent

  it.each([
    ['appearance', 'General'], ['updates', 'General'], ['vocabulary', 'Words'], ['review', 'Cards'],
    ['card-layout', 'Cards'], ['ai-model', 'Cards'], ['tts', 'Cards'], ['pictures', 'Cards'],
    ['books', 'Sources'], ['media-storage', 'Sources'],
  ])('opens the section that took over %s', (old, section) => {
    open(`?section=${old}`)

    expect(current()).toBe(section)
  })

  it.each([['known-words', 'Known0'], ['learning', 'Learning0'], ['unknown-words', 'Marked unknown0']])(
    'opens the word list that took over %s', (old, list) => {
      open(`?section=${old}`)

      expect(current()).toBe('Words')
      expect(tab()).toBe(list)
    },
  )

  it('opens General when no section is asked for', () => {
    open('')

    expect(current()).toBe('General')
  })
})
