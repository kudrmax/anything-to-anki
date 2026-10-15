import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { RebuildCounts, SourceOperation } from '@/api/types'
import { RebuildDialog } from './RebuildDialog'

const SOURCE = 7
const NOTHING: RebuildCounts = {
  words_added: 0, words_removed: 0, cards_new_phrase: 0, cards_text_reset: 0, cards_without_generation: 0, nothing_to_update: true,
}
const CHANGES: RebuildCounts = {
  words_added: 3, words_removed: 1, cards_new_phrase: 2, cards_text_reset: 4, cards_without_generation: 5, nothing_to_update: false,
}
const operation = (kind: SourceOperation['kind'], state: SourceOperation['state'], extra: Partial<SourceOperation> = {}): SourceOperation => ({
  operation_id: 1, kind, state, caption: `${kind} caption`, preview: null, summary: null, refresh: null, error: null, ...extra,
})

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

  const open = (kind: 'rebuild' | 'refresh' = 'rebuild') => act(() => root.render(
    <RebuildDialog sourceId={SOURCE} title="Pilot" operation={kind} onFinished={onFinished} onClose={() => {}} />,
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
  })

  it('shows the preview lines and applies with the checkbox', async () => {
    vi.spyOn(api, 'previewRebuild').mockResolvedValue(operation('preview', 'running'))
    const state = vi.spyOn(api, 'getOperation').mockResolvedValueOnce(operation('preview', 'running'))
    open()
    await press('Preview')
    expect(dialog().textContent).toContain('preview caption')
    expect(button('Close')).toBeDefined()
    expect(button('Cancel')).toBeUndefined()

    state.mockResolvedValue(operation('preview', 'done', { preview: { without_open: NOTHING, with_open: CHANGES } }))
    await poll()
    await poll()
    expect(dialog().textContent).toContain('Nothing to update')
    expect(button('Rebuild')).toBeUndefined()

    act(() => (dialog().querySelector('[role="switch"]') as HTMLElement).click())
    expect(dialog().textContent).toContain('2 cards get a different phrase — need ✨ again')
    expect(dialog().textContent).toContain("4 cards' text changed — their generation is reset")

    const rebuild = vi.spyOn(api, 'rebuildSource').mockResolvedValue(operation('rebuild', 'running', { operation_id: 2 }))
    state.mockResolvedValue(operation('rebuild', 'done', { operation_id: 2, summary: { include_open: true, counts: CHANGES } }))
    await press('Rebuild')
    expect(rebuild).toHaveBeenCalledWith(SOURCE, true)
    await poll()
    expect(dialog().textContent).toContain('5 cards without generation')
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it('shows why an operation could not start', async () => {
    vi.spyOn(api, 'previewRebuild').mockRejectedValue(new Error('409: {"detail":"Source 7 is busy with rebuild"}'))
    open()
    await press('Preview')
    expect(dialog().textContent).toContain('Source 7 is busy with rebuild')
  })

  it('refreshes a topic and says what it added', async () => {
    vi.spyOn(api, 'refreshTopic').mockResolvedValue(operation('refresh', 'running'))
    vi.spyOn(api, 'getOperation').mockResolvedValue(
      operation('refresh', 'done', { refresh: { words_added: 1, phrases_added: 4, phrases_replaced: 0 } }),
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

  it('offers no Rebuild when there is nothing to update', async () => {
    await previewed({ without_open: NOTHING, with_open: NOTHING })
    expect(dialog().textContent).toContain('Nothing to update')
    expect(button('Rebuild')).toBeUndefined()
  })

  it('shows the error when the applied rebuild fails', async () => {
    const state = await previewed({ without_open: CHANGES, with_open: CHANGES })
    vi.spyOn(api, 'rebuildSource').mockResolvedValue(operation('rebuild', 'running', { operation_id: 2 }))
    state.mockResolvedValue(operation('rebuild', 'error', { operation_id: 2, error: 'UNIQUE constraint failed' }))
    await press('Rebuild')
    await poll()
    expect(dialog().querySelector('[role="alert"]')?.textContent).toContain('UNIQUE constraint failed')
    expect(onFinished).not.toHaveBeenCalled()
  })

  it('stops following when another operation took the source over', async () => {
    vi.spyOn(api, 'previewRebuild').mockResolvedValue(operation('preview', 'running'))
    const state = vi.spyOn(api, 'getOperation').mockResolvedValue(operation('rebuild', 'done', { operation_id: 9 }))
    open()
    await press('Preview')
    await poll()
    expect(dialog().querySelector('[role="alert"]')?.textContent).toContain('Another operation ran on this source')
    const calls = state.mock.calls.length
    await poll()
    expect(state.mock.calls.length).toBe(calls)
  })
})
