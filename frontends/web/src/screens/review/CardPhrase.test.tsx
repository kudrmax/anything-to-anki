import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CandidateCloze } from '@/api/types'
import { CardPhrase } from './CardPhrase'
import { reviewCard } from './reviewFixtures'
import type { ClozeEditor } from './useClozeEditor'
import type { PhraseEditor } from './usePhraseEditor'

const CLOZE: CandidateCloze = { hidden_word_indices: [1], hint_kind: 'none', custom_hint: null }

describe('CardPhrase of a cloze card', () => {
  let host: HTMLDivElement
  let root: Root
  const editor = { draft: null, saving: false, start: vi.fn() } as unknown as PhraseEditor
  let cloze: ClozeEditor

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
    cloze = { active: false, start: vi.fn() } as unknown as ClozeEditor
  })

  afterEach(() => act(() => root.unmount()))

  const render = (canEdit: boolean) =>
    act(() => root.render(<CardPhrase candidate={reviewCard({ choice: 'cloze', cloze: CLOZE, can_edit_cloze: canEdit })} editor={editor} cloze={cloze} />))
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
