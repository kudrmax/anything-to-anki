import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { notifyLongOperation, onLongOperationFinished } from '@/api/longOperationSignal'
import type { LongOperationStatus } from '@/api/types'
import { LongOperationBlocker, LongOperationOverlay } from './LongOperationOverlay'
import { useLongOperation } from './useLongOperation'

const idle: LongOperationStatus = { operation_id: 0, kind: null, running: false, percent: 0, cancellable: false, outcome: null, error: null }
const running = (percent: number, cancellable = true): LongOperationStatus => (
  { operation_id: 1, kind: 'level_change', running: true, percent, cancellable, outcome: null, error: null }
)

describe('LongOperationBlocker', () => {
  let root: Root
  let host: HTMLDivElement

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  it('shows the percent and a cancel button', () => {
    act(() => root.render(<LongOperationBlocker label="Processing sources" percent={37} cancellable onCancel={() => {}} />))

    expect(host.textContent).toContain('37%')
    expect(host.querySelector('[role=alertdialog]')?.getAttribute('aria-label')).toBe('Processing sources')
    expect(host.querySelector('button')?.disabled).toBe(false)
  })

  it('disables cancel when the change is past cancelling', () => {
    act(() => root.render(<LongOperationBlocker label="Changing level" percent={90} cancellable={false} onCancel={() => {}} />))

    expect(host.querySelector('button')?.disabled).toBe(true)
  })
})

describe('LongOperationOverlay', () => {
  let root: Root
  let host: HTMLDivElement
  let replies: LongOperationStatus[]

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    replies = [idle]
    vi.spyOn(api, 'getLongOperation').mockImplementation(async () => replies.shift() ?? idle)
    host = document.body.appendChild(document.createElement('div'))
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
    vi.restoreAllMocks()
  })

  it('appears when a write is refused for a running level change', async () => {
    await act(async () => root.render(<LongOperationOverlay />))
    expect(document.body.textContent).not.toContain('%')
    expect(api.getLongOperation).toHaveBeenCalledTimes(1)

    replies = [running(42)]
    await act(async () => notifyLongOperation())

    expect(document.body.textContent).toContain('42%')
  })

  it('shows why a failed change left the level as it was', async () => {
    replies = [running(10)]
    await act(async () => root.render(<LongOperationOverlay />))

    replies = [{ ...idle, operation_id: 1, outcome: 'failed', error: 'source 3 broke' }]
    await act(async () => notifyLongOperation())

    expect(document.body.textContent).not.toContain('10%')
    expect(document.body.textContent).toContain('source 3 broke')
  })

  it('tells about a change that ended before it was ever seen running', async () => {
    await act(async () => root.render(<LongOperationOverlay />))

    replies = [{ ...idle, operation_id: 1, outcome: 'failed', error: 'source 3 broke' }]
    await act(async () => notifyLongOperation())

    expect(document.body.textContent).toContain('source 3 broke')
  })

  it('says nothing about a change that ended before the page was opened', async () => {
    replies = [{ ...idle, operation_id: 4, outcome: 'failed', error: 'old news' }]
    await act(async () => root.render(<LongOperationOverlay />))
    await act(async () => notifyLongOperation())

    expect(document.body.textContent).not.toContain('old news')
  })

  it('names what failed by the kind of the operation', async () => {
    replies = [{ ...running(10), kind: 'process' }]
    await act(async () => root.render(<LongOperationOverlay />))

    replies = [{ ...idle, operation_id: 1, kind: 'process', outcome: 'failed', error: 'disk full' }]
    await act(async () => notifyLongOperation())

    expect(document.body.textContent).toContain('Sources were not processed — disk full')
  })
})

describe('useLongOperation', () => {
  let root: Root
  let host: HTMLDivElement
  let replies: LongOperationStatus[]
  const reload = vi.fn()

  function Probe() {
    useLongOperation(reload)
    return null
  }

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    reload.mockReset()
    vi.spyOn(api, 'getLongOperation').mockImplementation(async () => replies.shift() ?? idle)
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.restoreAllMocks()
  })

  async function endOf(kind: LongOperationStatus['kind']): Promise<number> {
    let finished = 0
    const unsubscribe = onLongOperationFinished(() => { finished += 1 })
    replies = [{ ...running(50), kind }]
    await act(async () => root.render(<Probe />))
    replies = [{ ...idle, operation_id: 1, kind, outcome: 'succeeded', percent: 100 }]
    await act(async () => notifyLongOperation())
    unsubscribe()
    return finished
  }

  it('reloads the page once the level is changed', async () => {
    expect(await endOf('level_change')).toBe(0)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('tells the screens, without a reload, once an operation over sources ends', async () => {
    expect(await endOf('update')).toBe(1)
    expect(reload).not.toHaveBeenCalled()
  })
})
