import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SourceDocument } from '@/api/types'
import { SourceTexts } from './SourceTexts'

const doc = (sourceId: number, title: string): SourceDocument => ({
  source_id: sourceId,
  title,
  blocks: [{ type: 'paragraph', lines: [{ text: `Text of ${title}.` }], level: null, mode: 'flow', ordered: null, depth: null }],
  highlights: [],
}) as unknown as SourceDocument

const noop = () => {}

describe('SourceTexts', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.unstubAllGlobals()
  })

  const render = (editingSourceId: number | null) => act(() => root.render(
    <SourceTexts
      documents={[doc(2, 'Episode 2'), doc(1, 'Pilot')]}
      candidates={[]}
      focusId={null}
      editingSourceId={editingSourceId}
      onWordClick={noop}
      onTextSelected={noop}
    />,
  ))
  const titles = () => [...host.querySelectorAll('h3')].map(h => h.textContent)
  const selectableTitles = () =>
    [...host.querySelectorAll('[data-selectable]')].map(section => section.querySelector('h3')?.textContent)

  it('stacks every source text under its title, in set order', () => {
    render(null)
    expect(titles()).toEqual(['Episode 2', 'Pilot'])
    expect(host.textContent).toContain('Text of Pilot.')
  })

  it('takes selections in every text while nothing is edited', () => {
    render(null)
    expect(selectableTitles()).toEqual(['Episode 2', 'Pilot'])
  })

  it('while a boundary is edited, only that source takes selections', () => {
    render(1)
    expect(selectableTitles()).toEqual(['Pilot'])
  })
})
