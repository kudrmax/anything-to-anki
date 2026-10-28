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
  missing: [], generating: [], cannot_fill: [], is_cloze: false,
}
const SECTION: ExportSection = { source_id: 1, source_title: 'Episode', cards: [CARD] }
const EXPORT: GlobalExport = {
  title: 'Friends', ready: [SECTION], incomplete: [], exported_count: 0,
  fill: { fillable: 0, generating: 0, skipped: [] },
}
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

  const open = async (entry: string | { pathname: string; search: string; state: unknown } = `/export?scope=${SCOPE_ID}`) => {
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={[entry]}>
          <Routes><Route path="/export" element={<ExportScreen />} /></Routes>
        </MemoryRouter>,
      )
    })
  }

  it('loads the scope and shows its title', async () => {
    const cards = vi.spyOn(api, 'getExportCards').mockResolvedValue(EXPORT)
    await open()
    expect(cards).toHaveBeenCalledWith(SCOPE_ID)
    expect(container.querySelector('h1')?.textContent).toBe('Friends')
  })

  it('syncs within the scope', async () => {
    vi.spyOn(api, 'getExportCards').mockResolvedValue(EXPORT)
    const sync = vi.spyOn(api, 'syncToAnki').mockResolvedValue(SYNCED)
    await open()
    const button = [...container.querySelectorAll('button')].find(b => b.textContent?.includes('Add to Anki'))
    await act(async () => { button?.click() })
    expect(sync).toHaveBeenCalledWith('ready', SCOPE_ID)
  })

  it('exports a single source through its scope', async () => {
    const cards = vi.spyOn(api, 'getExportCards').mockResolvedValue(EXPORT)
    await open('/export?scope=source-7')
    expect(cards).toHaveBeenCalledWith('source-7')
  })

  it('goes back only where the opening screen asked', async () => {
    vi.spyOn(api, 'getExportCards').mockResolvedValue(EXPORT)
    await open()
    expect(container.querySelector('[aria-label="Back"]')).toBeNull()
    act(() => root.unmount())
    root = createRoot(container)
    await open({ pathname: '/export', search: '?scope=source-7', state: { back: '/review?scope=source-7' } })
    expect(container.querySelector('[aria-label="Back"]')).not.toBeNull()
  })

  it('generates what incomplete cards lack and says what it skips', async () => {
    const incomplete: ExportSection = {
      ...SECTION,
      cards: [{
        ...CARD, missing: ['meaning', 'audio'], generating: ['meaning'],
        cannot_fill: [{ part: 'audio', reason: 'video_not_downloaded' }],
      }],
    }
    vi.spyOn(api, 'getExportCards').mockResolvedValue({
      ...EXPORT, ready: [], incomplete: [incomplete],
      fill: { fillable: 2, generating: 0, skipped: [{ reason: 'video_not_downloaded', cards: 1 }] },
    })
    const fill = vi.spyOn(api, 'fillMissing').mockResolvedValue({ ...EXPORT, ready: [], incomplete: [incomplete] })
    await open()
    expect(container.textContent).toContain("Can't generate: 1 card without the video")
    expect(container.textContent).toContain('Generating meaning · No audio (video not downloaded)')
    const button = [...container.querySelectorAll('button')].find(b => b.textContent?.includes('Generate missing · 2 cards'))
    await act(async () => { button?.click() })
    expect(fill).toHaveBeenCalledWith(SCOPE_ID)
  })

  it('shows the empty state when everything is in Anki', async () => {
    vi.spyOn(api, 'getExportCards').mockResolvedValue({ ...EXPORT, ready: [], exported_count: 3 })
    await open()
    expect(container.textContent).toContain('Everything marked for learning is already in Anki.')
  })
})
