import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { RebuildCounts, RebuildPreview, SetOperation, SetScope, SourceOperation } from '@/api/types'
import { RebuildDialog } from './RebuildDialog'

const SOURCE: SetScope = 'source-7'
const DONE_WELL = { skipped: 0, failed: 0 }
const NOTHING: RebuildCounts = {
  words_added: 0, words_removed: 0, cards_lost_generation: 0, cards_moved: 0,
  cards_recut: 0, cards_recut_lost_text_generation: 0, nothing_to_update: true,
}
const CHANGES: RebuildCounts = {
  words_added: 3, words_removed: 1, cards_lost_generation: 2, cards_moved: 4,
  cards_recut: 0, cards_recut_lost_text_generation: 0, nothing_to_update: false,
}
const RECUT: RebuildCounts = { ...CHANGES, cards_recut: 6, cards_recut_lost_text_generation: 5 }
const operation = (kind: SourceOperation['kind'], state: SourceOperation['state'], extra: Partial<SourceOperation> = {}): SourceOperation => ({
  operation_id: 1, kind, state, caption: `${kind} caption`, preview: null, summary: null, refresh: null, error: null, ...extra,
})
const updatePreview = (counts: RebuildCounts, outcome = DONE_WELL): RebuildPreview => ({ mode: 'update', counts, ...outcome })

describe('RebuildDialog', () => {
  let root: Root
  const onFinished = vi.fn()

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.useFakeTimers()
    onFinished.mockReset()
    root = createRoot(document.createElement('div'))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  const open = (kind: SetOperation = 'update', scope: SetScope = SOURCE) => act(() => root.render(
    <RebuildDialog scope={scope} title="Pilot" operation={kind} onFinished={onFinished} onClose={() => {}} />,
  ))
  const dialog = () => document.body.querySelector('[role="dialog"]') as HTMLElement
  const button = (label: string) => [...dialog().querySelectorAll('button')].find(b => b.textContent === label)
  const press = async (label: string) => { await act(async () => { button(label)?.click() }) }
  const poll = async () => { await act(async () => { await vi.advanceTimersByTimeAsync(1000) }) }

  it('does nothing until Preview is pressed', () => {
    const preview = vi.spyOn(api, 'previewRebuild')
    open()
    expect(preview).not.toHaveBeenCalled()
    expect(button('Preview')).toBeDefined()
    expect(dialog().textContent).toContain('Update “Pilot”')
    expect(dialog().textContent).toContain('Phrase texts and their Polish, Meaning and audio stay')
  })

  it('previews an update, applies it and says what changed', async () => {
    const preview = vi.spyOn(api, 'previewRebuild').mockResolvedValue(operation('preview', 'running'))
    const state = vi.spyOn(api, 'getOperation').mockResolvedValueOnce(operation('preview', 'running'))
    open()
    await press('Preview')
    expect(preview).toHaveBeenCalledWith(SOURCE, 'update')
    expect(dialog().textContent).toContain('preview caption')
    expect(button('Close')).toBeDefined()
    expect(button('Cancel')).toBeUndefined()

    state.mockResolvedValue(operation('preview', 'done', { preview: updatePreview(CHANGES) }))
    await poll()
    await poll()
    expect(dialog().textContent).toContain('3 new words, 1 word removed')
    expect(dialog().textContent).toContain('2 removed cards had Polish, Meaning or audio')
    expect(dialog().textContent).toContain('4 cards move to a simpler sentence — need ✨ there')
    expect(dialog().textContent).toContain('The numbers may differ slightly')
    expect(dialog().querySelector('[role="switch"]')).toBeNull()

    const rebuild = vi.spyOn(api, 'rebuild').mockResolvedValue(operation('update', 'running', { operation_id: 2 }))
    state.mockResolvedValue(operation('update', 'done', { operation_id: 2, summary: { mode: 'update', counts: CHANGES, ...DONE_WELL } }))
    await press('Update')
    expect(rebuild).toHaveBeenCalledWith(SOURCE, 'update')
    await poll()
    expect(dialog().textContent).toContain('3 new words, 1 word removed')
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it('previews and applies a re-cut, saying what the new cuts lose', async () => {
    const preview = vi.spyOn(api, 'previewRebuild').mockResolvedValue(operation('preview', 'running'))
    const state = vi.spyOn(api, 'getOperation').mockResolvedValue(
      operation('preview', 'done', { preview: { mode: 'recut', counts: RECUT, ...DONE_WELL } }),
    )
    open('recut')
    expect(dialog().textContent).toContain('Re-cut phrases of “Pilot”')
    expect(dialog().textContent).toContain('A phrase that changes loses its Polish, audio and video; Meaning stays')
    await press('Preview')
    await poll()
    expect(preview).toHaveBeenCalledWith(SOURCE, 'recut')
    expect(dialog().textContent).toContain('6 phrases get a new cut')
    expect(dialog().textContent).toContain('5 of them lose Polish or audio')

    const rebuild = vi.spyOn(api, 'rebuild').mockResolvedValue(operation('recut', 'running', { operation_id: 2 }))
    state.mockResolvedValue(operation('recut', 'done', { operation_id: 2, summary: { mode: 'recut', counts: RECUT, ...DONE_WELL } }))
    await press('Re-cut')
    expect(rebuild).toHaveBeenCalledWith(SOURCE, 'recut')
  })

  it('shows why an operation could not start', async () => {
    vi.spyOn(api, 'previewRebuild').mockRejectedValue(new Error('409: {"detail":"Source 7 is busy with update"}'))
    open()
    await press('Preview')
    expect(dialog().textContent).toContain('Source 7 is busy with update')
  })

  it('refreshes a topic and says what it added', async () => {
    vi.spyOn(api, 'refresh').mockResolvedValue(operation('refresh', 'running'))
    vi.spyOn(api, 'getOperation').mockResolvedValue(
      operation('refresh', 'done', { refresh: { words_added: 1, phrases_added: 4, ...DONE_WELL } }),
    )
    open('refresh')
    await press('Refresh')
    await poll()
    expect(dialog().textContent).toContain('1 word and 4 phrases added')
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  const previewed = async (preview: SourceOperation['preview']) => {
    vi.spyOn(api, 'previewRebuild').mockResolvedValue(operation('preview', 'running'))
    const state = vi.spyOn(api, 'getOperation').mockResolvedValue(operation('preview', 'done', { preview }))
    open()
    await press('Preview')
    await poll()
    return state
  }

  it('says the source is up to date and offers only Close when nothing changes', async () => {
    await previewed(updatePreview(NOTHING))
    expect(dialog().textContent).toContain('Already up to date')
    expect(dialog().textContent).not.toContain('The numbers may differ slightly')
    expect(button('Update')).toBeUndefined()
    expect(button('Close')).toBeDefined()
  })

  it('offers Update when the preview has changes but no new words', async () => {
    const SECTIONS_ONLY: RebuildCounts = { ...NOTHING, nothing_to_update: false }
    await previewed(updatePreview(SECTIONS_ONLY))
    expect(button('Update')).toBeDefined()
    expect(dialog().textContent).toContain('0 new words, 0 words removed')
    expect(dialog().textContent).not.toContain('Already up to date')
  })

  it('shows the error when the applied update fails', async () => {
    const state = await previewed(updatePreview(CHANGES))
    vi.spyOn(api, 'rebuild').mockResolvedValue(operation('update', 'running', { operation_id: 2 }))
    state.mockResolvedValue(operation('update', 'error', { operation_id: 2, error: 'UNIQUE constraint failed' }))
    await press('Update')
    await poll()
    expect(dialog().querySelector('[role="alert"]')?.textContent).toContain('UNIQUE constraint failed')
    expect(onFinished).not.toHaveBeenCalled()
  })

  it('stops following when another operation took the source over', async () => {
    vi.spyOn(api, 'previewRebuild').mockResolvedValue(operation('preview', 'running'))
    const state = vi.spyOn(api, 'getOperation').mockResolvedValue(operation('update', 'done', { operation_id: 9 }))
    open()
    await press('Preview')
    await poll()
    expect(dialog().querySelector('[role="alert"]')?.textContent).toContain('Another operation ran on these sources')
    const calls = state.mock.calls.length
    await poll()
    expect(state.mock.calls.length).toBe(calls)
  })

  it('runs on a collection the same way and says which sources it did not reach', async () => {
    const preview = vi.spyOn(api, 'previewRebuild').mockResolvedValue(operation('preview', 'running'))
    vi.spyOn(api, 'getOperation').mockResolvedValue(operation('preview', 'done', {
      preview: updatePreview(CHANGES, { skipped: 2, failed: 1 }),
    }))
    open('update', 3)
    await press('Preview')
    await poll()
    expect(preview).toHaveBeenCalledWith(3, 'update')
    expect(dialog().textContent).toContain('2 sources were busy and skipped')
    expect(dialog().textContent).toContain('1 source failed')
  })

  it('says nothing about skipped or failed sources of a single source', async () => {
    await previewed(updatePreview(CHANGES))
    expect(dialog().textContent).not.toContain('skipped')
    expect(dialog().textContent).not.toContain('failed')
  })
})
