import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { AnkiStatus, CardPreview, ExportSection, GlobalExport, SyncResult } from '@/api/types'
import { ExportScreen } from './ExportScreen'

const SCOPE_ID = 12
const CARD: CardPreview = {
  candidate_id: 5, phrase_id: 7, lemma: 'run', sentence: 'I <b>run</b>.', meaning: null, translation: null,
  synonyms: null, examples: null, ipa: null, screenshot_url: null, audio_url: null,
  pronunciation_us_url: null, pronunciation_uk_url: null, tts_audio_url: null,
  missing: [], is_cloze: false,
}
const SECTION: ExportSection = { source_id: 1, source_title: 'Episode', cards: [CARD] }
const EXPORT: GlobalExport = { title: 'Friends', ready: [SECTION], incomplete: [], exported_count: 0 }
const ANKI: AnkiStatus = { available: true, version: 6, note_type_problems: [] }
const SYNCED: SyncResult = { total: 1, added: 1, skipped: 0, errors: 0, skipped_lemmas: [], error_lemmas: [] }

describe('ExportScreen scope', () => {
  let root: Root
  let container: HTMLElement

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.spyOn(api, 'getAnkiStatus').mockResolvedValue(ANKI)
    vi.spyOn(api, 'getSettings').mockResolvedValue(null as never)
    container = document.createElement('div')
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.restoreAllMocks()
  })

  const open = async () => {
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={[`/export?scope=${SCOPE_ID}`]}>
          <Routes><Route path="/export" element={<ExportScreen />} /></Routes>
        </MemoryRouter>,
      )
    })
  }

  it('loads the scope and shows its title', async () => {
    const cards = vi.spyOn(api, 'getExportCards').mockResolvedValue(EXPORT)
    await open()
    expect(cards).toHaveBeenCalledWith(undefined, SCOPE_ID)
    expect(container.querySelector('h1')?.textContent).toBe('Friends')
  })

  it('syncs within the scope', async () => {
    vi.spyOn(api, 'getExportCards').mockResolvedValue(EXPORT)
    const sync = vi.spyOn(api, 'syncToAnki').mockResolvedValue(SYNCED)
    await open()
    const button = [...container.querySelectorAll('button')].find(b => b.textContent?.includes('Add to Anki'))
    await act(async () => { button?.click() })
    expect(sync).toHaveBeenCalledWith('ready', undefined, SCOPE_ID)
  })
})
