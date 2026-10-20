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

  const render = (editingSourceId: number | null, documents = [doc(2, 'Episode 2'), doc(1, 'Pilot')]) => act(() => root.render(
    <SourceTexts
      documents={documents}
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

  const toggle = (title: string) => {
    const button = [...host.querySelectorAll('h3 button')].find(b => b.textContent?.includes(title))
    act(() => (button as HTMLButtonElement).click())
  }

  it('folds a source text to its title and unfolds it back', () => {
    render(null)
    toggle('Pilot')
    expect(host.textContent).not.toContain('Text of Pilot.')
    expect(host.textContent).toContain('Text of Episode 2.')
    expect(host.querySelector('[data-source-id="1"] button')?.getAttribute('aria-expanded')).toBe('false')
    toggle('Pilot')
    expect(host.textContent).toContain('Text of Pilot.')
  })

  it('a single source has nothing to fold', () => {
    render(null, [doc(1, 'Pilot')])
    expect(host.querySelector('h3 button')).toBeNull()
    expect(titles()).toEqual(['Pilot'])
  })
})
