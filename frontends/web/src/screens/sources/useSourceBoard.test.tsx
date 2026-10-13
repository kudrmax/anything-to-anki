import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { Scope, SourceBoard } from '@/api/types'
import { useSourceBoard } from './useSourceBoard'

const callbacks = { onMissingScope: vi.fn(), onError: vi.fn(), onChanged: vi.fn() }
const board = (title: string): SourceBoard => ({ title, groups: [] })

function Probe({ scope, onRender }: { scope: Scope; onRender: (result: ReturnType<typeof useSourceBoard>) => void }) {
  onRender(useSourceBoard(scope, '', {
    onMissingScope: () => callbacks.onMissingScope(),
    onError: m => callbacks.onError(m),
    onChanged: () => callbacks.onChanged(),
  }))
  return null
}

const flush = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })

describe('useSourceBoard', () => {
  let root: Root
  let latest: ReturnType<typeof useSourceBoard>

  const render = (scope: Scope) =>
    act(async () => root.render(<Probe scope={scope} onRender={result => { latest = result }} />))

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

    await render(42)
    await flush()

    expect(callbacks.onMissingScope).toHaveBeenCalledTimes(1)
    expect(callbacks.onError).not.toHaveBeenCalled()
  })

  it('reports other failures as errors', async () => {
    vi.spyOn(api, 'getSourceBoard').mockRejectedValue(new Error('500: boom'))

    await render(42)
    await flush()

    expect(callbacks.onMissingScope).not.toHaveBeenCalled()
    expect(callbacks.onError).toHaveBeenCalledTimes(1)
  })

  it('fresh inline callbacks on every render do not refetch the board', async () => {
    const getBoard = vi.spyOn(api, 'getSourceBoard').mockResolvedValue(board('A'))

    await render('all')
    await flush()
    await render('all')
    await flush()

    expect(getBoard).toHaveBeenCalledTimes(1)
  })

  it('a late answer for the previous scope never replaces the current board', async () => {
    const resolvers: Record<string, (b: SourceBoard) => void> = {}
    vi.spyOn(api, 'getSourceBoard').mockImplementation(scope => new Promise(resolve => {
      resolvers[String(scope)] = resolve
    }))

    await render('all')
    await flush()
    await render('unsorted')
    await flush()
    await act(async () => resolvers.unsorted(board('B')))
    await act(async () => resolvers.all(board('A')))

    expect(latest.board?.title).toBe('B')
  })

  it('says how many sources a batch process could not start', async () => {
    vi.spyOn(api, 'getSourceBoard').mockResolvedValue(board('A'))
    vi.spyOn(api, 'processSources').mockResolvedValue({ started: [1], skipped: [2, 3] })

    await render('all')
    await flush()
    await act(async () => latest.processSelected([1, 2, 3]))

    expect(callbacks.onError).toHaveBeenCalledWith("2 sources can't be processed right now")
  })

  it('stays quiet when every source started', async () => {
    vi.spyOn(api, 'getSourceBoard').mockResolvedValue(board('A'))
    vi.spyOn(api, 'processPending').mockResolvedValue({ started: [1], skipped: [] })

    await render('all')
    await flush()
    await act(async () => latest.processPending())

    expect(callbacks.onError).not.toHaveBeenCalled()
  })
})
