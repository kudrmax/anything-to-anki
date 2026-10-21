import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { notifyLevelChange } from '@/api/levelChangeSignal'
import type { LevelChangeStatus } from '@/api/types'
import { LevelChangeBlocker, LevelChangeOverlay } from './LevelChangeOverlay'

const idle: LevelChangeStatus = { running: false, percent: 0, cancellable: false, outcome: null, error: null }
const running = (percent: number, cancellable = true): LevelChangeStatus => (
  { running: true, percent, cancellable, outcome: null, error: null }
)

describe('LevelChangeBlocker', () => {
  let root: Root
  let host: HTMLDivElement

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  it('shows the percent and a cancel button', () => {
    act(() => root.render(<LevelChangeBlocker percent={37} cancellable onCancel={() => {}} />))

    expect(host.textContent).toContain('37%')
    expect(host.querySelector('button')?.disabled).toBe(false)
  })

  it('disables cancel when the change is past cancelling', () => {
    act(() => root.render(<LevelChangeBlocker percent={90} cancellable={false} onCancel={() => {}} />))

    expect(host.querySelector('button')?.disabled).toBe(true)
  })
})

describe('LevelChangeOverlay', () => {
  let root: Root
  let host: HTMLDivElement
  let replies: LevelChangeStatus[]

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    replies = [idle]
    vi.spyOn(api, 'getLevelChange').mockImplementation(async () => replies.shift() ?? idle)
    host = document.body.appendChild(document.createElement('div'))
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
    vi.restoreAllMocks()
  })

  it('appears when a write is refused for a running level change', async () => {
    await act(async () => root.render(<LevelChangeOverlay />))
    expect(document.body.textContent).not.toContain('%')
    expect(api.getLevelChange).toHaveBeenCalledTimes(1)

    replies = [running(42)]
    await act(async () => notifyLevelChange())

    expect(document.body.textContent).toContain('42%')
  })

  it('shows why a failed change left the level as it was', async () => {
    replies = [running(10)]
    await act(async () => root.render(<LevelChangeOverlay />))

    replies = [{ ...idle, outcome: 'failed', error: 'source 3 broke' }]
    await act(async () => notifyLevelChange())

    expect(document.body.textContent).not.toContain('10%')
    expect(document.body.textContent).toContain('source 3 broke')
  })
})
