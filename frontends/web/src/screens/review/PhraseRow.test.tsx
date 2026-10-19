import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Shown } from '@/api/types'
import dot from '@/ui/StatusDot.module.css'
import { PhraseRow } from './PhraseRow'
import { reviewCard } from './reviewFixtures'

describe('PhraseRow', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const toneOf = (shown: Shown, isDone = true) => {
    act(() => root.render(<PhraseRow candidate={reviewCard({ shown, is_done: isDone })} onSelect={() => {}} />))
    return host.querySelector('button > span:first-child:not([class*="queueText"])')?.className ?? null
  }

  it.each([
    [{ status: 'learn', skipped: true, where: 'here', tone: 'learning' }, dot.ok],
    [{ status: 'known', skipped: false, where: 'other_card', tone: 'settled' }, dot.off],
    [{ status: 'new', skipped: true, where: 'nowhere', tone: 'settled' }, dot.off],
  ] as [Shown, string][])('tones a done card by the tone the backend sent: %o', (shown, tone) => {
    expect(toneOf(shown)).toContain(tone)
  })

  it('shows no dot on an open card', () => {
    expect(toneOf({ status: 'new', skipped: false, where: 'nowhere', tone: 'open' }, false)).toBeNull()
  })
})
