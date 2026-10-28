import { act, useEffect } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSettings, type SettingsStore } from './useSettings'

const { api } = vi.hoisted(() => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    getAnalysisKeys: vi.fn(),
  } as Record<string, ReturnType<typeof vi.fn>>,
}))

vi.mock('@/api/client', () => ({
  api: new Proxy(api, { get: (target, name: string) => target[name] ?? (() => Promise.resolve([])) }),
}))

const LOADED = {
  ai_model: 'sonnet', cefr_level: 'B2', anki_deck_name: 'Default', usage_group_order: ['a', 'b'],
  source_grouping: 'stage', source_sort: 'added', source_sort_direction: 'reverse',
}
const AUTOSAVE_WAIT_MS = 1000

describe('useSettings autosave', () => {
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
    vi.useFakeTimers({ shouldAdvanceTime: true })
    ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    Object.values(api).forEach(fn => fn.mockReset())
    api.getSettings.mockResolvedValue(LOADED)
    api.updateSettings.mockImplementation(changes => Promise.resolve({ ...LOADED, ...changes }))
    api.getAnalysisKeys.mockResolvedValue(['cefr_level', 'frequent_word_threshold'])
    host = document.createElement('div')
    root = createRoot(host)
    await act(async () => root.render(<Probe />))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.useRealTimers()
  })

  const settle = () => act(async () => { await vi.advanceTimersByTimeAsync(AUTOSAVE_WAIT_MS) })

  it('saves a change on its own, sending only what changed', async () => {
    act(() => store().change('ai_model', 'opus'))
    await settle()

    expect(api.updateSettings).toHaveBeenCalledExactlyOnceWith({ ai_model: 'opus' })
    expect(store().form?.ai_model).toBe('opus')
  })

  it('sends quick changes in one request', async () => {
    act(() => store().change('ai_model', 'opus'))
    act(() => store().change('ai_model', 'haiku'))
    await settle()

    expect(api.updateSettings).toHaveBeenCalledExactlyOnceWith({ ai_model: 'haiku' })
  })

  it('saves typed text only once it is committed', async () => {
    act(() => store().edit('anki_deck_name', 'English'))
    await settle()
    expect(api.updateSettings).not.toHaveBeenCalled()

    await act(async () => store().commit())

    expect(api.updateSettings).toHaveBeenCalledExactlyOnceWith({ anki_deck_name: 'English' })
  })

  it('asks before a change that analyses every source again, and saves it only when confirmed', async () => {
    act(() => store().change('cefr_level', 'C1'))
    await settle()

    expect(api.updateSettings).not.toHaveBeenCalled()
    expect(store().confirming).toEqual({ key: 'cefr_level', value: 'C1' })
    expect(store().form?.cefr_level).toBe('B2')

    await act(async () => store().confirmChange())

    expect(api.updateSettings).toHaveBeenCalledExactlyOnceWith({ cefr_level: 'C1' })
    expect(store().confirming).toBeNull()
  })

  it('leaves the setting as it was when the change is cancelled', async () => {
    act(() => store().change('cefr_level', 'C1'))
    act(() => store().cancelChange())
    await settle()

    expect(api.updateSettings).not.toHaveBeenCalled()
    expect(store().form?.cefr_level).toBe('B2')
  })

  it('keeps a change that failed and sends it with the next one', async () => {
    api.updateSettings.mockRejectedValueOnce(new Error('500: {"detail":"disk full"}'))
    act(() => store().change('ai_model', 'opus'))
    await settle()
    expect(store().saveError).toBe('disk full')

    act(() => store().change('anki_deck_name', 'English'))
    await settle()

    expect(api.updateSettings).toHaveBeenLastCalledWith({ ai_model: 'opus', anki_deck_name: 'English' })
    expect(store().saveError).toBeNull()
  })
})
