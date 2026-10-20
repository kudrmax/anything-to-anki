import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SourceStatus } from '@/api/types'
import { offersProcess } from './processOffer'
import { ReviewAction } from './ReviewAction'

describe('ReviewAction', () => {
  let host: HTMLDivElement
  let root: Root
  const noop = () => {}

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const render = (status: SourceStatus, canReview: boolean, handlers = { onProcess: noop, onReview: noop }) =>
    act(() => root.render(<ReviewAction status={status} canReview={canReview} primary={false} {...handlers} />))

  it.each<[SourceStatus, boolean, string]>([
    ['new', true, 'Process'], ['error', false, 'Retry'], ['done', true, 'Review'],
    ['partially_reviewed', true, 'Continue'], ['reviewed', true, 'Open'], ['processing', true, ''],
  ])('%s → %s', (status, canReview, label) => {
    render(status, canReview)
    expect(host.textContent).toBe(label)
  })

  it('hides review on a scope that is not for review', () => {
    render('done', false)
    expect(host.textContent).toBe('')
  })

  it('processes from Process and Retry, and opens the review from Continue', () => {
    const onProcess = vi.fn()
    const onReview = vi.fn()
    render('error', false, { onProcess, onReview })
    act(() => host.querySelector('button')!.click())
    render('partially_reviewed', true, { onProcess, onReview })
    act(() => host.querySelector('button')!.click())
    expect(onProcess).toHaveBeenCalledOnce()
    expect(onReview).toHaveBeenCalledOnce()
  })

  it('offers processing only on new and failed sets', () => {
    expect((['new', 'error', 'processing', 'done', 'partially_reviewed', 'reviewed'] as SourceStatus[]).filter(offersProcess))
      .toEqual(['new', 'error'])
  })
})
