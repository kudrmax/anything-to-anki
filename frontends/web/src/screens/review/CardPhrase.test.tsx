import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CandidateCloze } from '@/api/types'
import { CardPhrase } from './CardPhrase'
import { reviewCard } from './reviewFixtures'
import type { ClozeEditor } from './useClozeEditor'
import type { PhraseEditor } from './usePhraseEditor'
import type { TargetEditor } from './useTargetEditor'

const CLOZE: CandidateCloze = { hidden_word_indices: [1], hint_kind: 'none', custom_hint: null }

describe('CardPhrase of a cloze card', () => {
  let host: HTMLDivElement
  let root: Root
  const editor = { draft: null, saving: false, start: vi.fn() } as unknown as PhraseEditor
  const target = { active: false } as unknown as TargetEditor
  let cloze: ClozeEditor

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
    cloze = { active: false, start: vi.fn() } as unknown as ClozeEditor
  })

  afterEach(() => act(() => root.unmount()))

  const render = (canEdit: boolean) =>
    act(() => root.render(<CardPhrase candidate={reviewCard({ choice: 'cloze', cloze: CLOZE, can_edit_cloze: canEdit })} editor={editor} cloze={cloze} target={target} />))
  const phrase = () => host.querySelector('p')!

  it('opens the markup editor on a click where the backend allows editing the cloze', () => {
    render(true)

    act(() => phrase().click())

    expect(cloze.start).toHaveBeenCalledOnce()
    expect(phrase().title).toBe('Click to change the hidden words')
  })

  it('keeps the hidden words of a cloze already in Anki', () => {
    render(false)

    act(() => phrase().click())

    expect(cloze.start).not.toHaveBeenCalled()
    expect(phrase().title).toBe('')
  })
})

describe('CardPhrase while the target is picked', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  it('makes every word a button and marks the picked ones as the target', () => {
    const editor = { draft: null, saving: false, start: vi.fn() } as unknown as PhraseEditor
    const cloze = { active: false } as unknown as ClozeEditor
    const toggleWord = vi.fn()
    const target = { active: true, picked: new Set([0, 3]), toggleWord } as unknown as TargetEditor
    act(() => root.render(<CardPhrase candidate={reviewCard()} editor={editor} cloze={cloze} target={target} />))

    const words = [...host.querySelectorAll('button')]
    act(() => words[2].click())

    expect(words.map(word => word.getAttribute('aria-pressed'))).toEqual(['true', 'false', 'false', 'true'])
    expect(toggleWord).toHaveBeenCalledWith(2)
  })
})
