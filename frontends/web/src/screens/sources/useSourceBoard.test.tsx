import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { useSourceBoard } from './useSourceBoard'

const callbacks = { onMissingScope: vi.fn(), onError: vi.fn(), onChanged: vi.fn() }

function Probe({ onRender }: { onRender: (result: ReturnType<typeof useSourceBoard>) => void }) {
  onRender(useSourceBoard(42, '', callbacks))
  return null
}

describe('useSourceBoard', () => {
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    Object.values(callbacks).forEach(fn => fn.mockReset())
    root = createRoot(document.createElement('div'))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.restoreAllMocks()
  })

  it('reports a missing scope when the board answers 404', async () => {
    vi.spyOn(api, 'getSourceBoard').mockRejectedValue(new Error('404: collection not found'))

    await act(async () => root.render(<Probe onRender={() => {}} />))
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })

    expect(callbacks.onMissingScope).toHaveBeenCalledTimes(1)
    expect(callbacks.onError).not.toHaveBeenCalled()
  })

  it('reports other failures as errors', async () => {
    vi.spyOn(api, 'getSourceBoard').mockRejectedValue(new Error('500: boom'))

    await act(async () => root.render(<Probe onRender={() => {}} />))
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })

    expect(callbacks.onMissingScope).not.toHaveBeenCalled()
    expect(callbacks.onError).toHaveBeenCalledTimes(1)
  })
})
