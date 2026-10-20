import { act, useEffect } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSettings, type SettingsStore } from './useSettings'

const { api } = vi.hoisted(() => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  } as Record<string, ReturnType<typeof vi.fn>>,
}))

vi.mock('@/api/client', () => ({
  api: new Proxy(api, { get: (target, name: string) => target[name] ?? (() => Promise.resolve([])) }),
}))

const LOADED = {
  ai_model: 'sonnet', usage_group_order: ['a', 'b'], source_grouping: 'stage', source_sort: 'added', source_sort_direction: 'reverse',
}

describe('useSettings save', () => {
  let host: HTMLDivElement
  let root: Root
  const latest: { store: SettingsStore | null } = { store: null }

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
    api.getSettings.mockResolvedValue(LOADED)
    api.updateSettings.mockResolvedValue(LOADED)
    host = document.createElement('div')
    root = createRoot(host)
    await act(async () => root.render(<Probe />))
  })

  afterEach(() => act(() => root.unmount()))

  it('leaves out the settings saved elsewhere, so a stale form cannot overwrite them', async () => {
    await act(async () => latest.store!.save())

    expect(api.updateSettings).toHaveBeenCalledWith({ ai_model: 'sonnet' })
  })
})
