import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { CardElement, CardLayoutRow, CardLayoutView } from '@/api/types'
import { CardLayoutEditingContext, shownColumns, type CardBlockContext, type CardLayoutEditing, type DragItem } from '@/cardLayout'
import { CardBody } from './CardBody'
import { reviewCard } from './reviewFixtures'

const STYLE = { size: 'm', tone: 'primary', bold: false, align: 'start', valign: 'baseline', space_top: 'none', space_right: 'none', space_bottom: 'none', space_left: 'none' } as const
const ELEMENTS: CardElement[] = ['target', 'translation', 'synonyms', 'transcription', 'picture']

const view = (...columns: CardLayoutRow[][]): CardLayoutView => ({
  layout: {
    columns: columns.map(rows => ({ width: 'normal', rows })),
    styles: ELEMENTS.map(element => ({ element, style: element === 'target' ? { ...STYLE, size: 'xl', tone: 'accent' } : STYLE })),
  },
  elements: ELEMENTS.map(element => ({ element, kind: element === 'picture' ? 'media' : 'text', can_hide: true })),
  hidden: [],
  can_add_column: true,
  can_remove_column: true,
})

const blocks = (...elements: CardElement[]): CardLayoutRow => ({ kind: 'blocks', elements })

const ctx = (): CardBlockContext => ({
  candidate: reviewCard({
    lemma: 'glare',
    meaning: { meaning: null, translation: 'сердито смотреть', synonyms: 'scowl', examples: null, ipa: '/ɡleər/', status: 'done', error: null, generated_at: null },
  }),
  media: { screenshotUrl: null, audioUrl: null, meaningImageUrl: null },
  playingUrl: null,
  togglePlay: () => {},
  keyAudioUrl: null,
  generating: false,
  generate: () => {},
  useExample: () => {},
  pictureSuggestions: null,
  showCefr: () => {},
})

describe('CardBody', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const render = (layout: CardLayoutView) =>
    act(() => root.render(<CardBody view={layout} columns={shownColumns(layout, ctx())} detailsOpen={false} onToggleDetails={() => {}} />))
  const shown = (column: Element) => Array.from(column.querySelectorAll('[data-element]')).map(block => block.getAttribute('data-element'))

  it('shows the elements where the layout puts them, rows of blocks side by side', () => {
    render(view([blocks('translation'), { kind: 'divider' }, blocks('target')], [blocks('transcription', 'synonyms')]))

    const [first, , second] = Array.from(host.children)
    expect(shown(first)).toEqual(['translation', 'target'])
    expect(first.querySelector('hr')).not.toBeNull()
    expect(shown(second)).toEqual(['transcription', 'synonyms'])
    expect(second.querySelectorAll('[data-element]')[0].parentElement).toBe(second.querySelectorAll('[data-element]')[1].parentElement)
  })

  it('styles a block as the layout says', () => {
    render(view([blocks('target')]))

    const target = host.querySelector('[data-element="target"]')!
    expect(target.getAttribute('data-size')).toBe('xl')
    expect(target.getAttribute('data-tone')).toBe('accent')
  })

  it('leaves out a block with nothing to show and a row left empty', () => {
    render(view([blocks('picture'), blocks('target', 'picture')]))

    const [first] = Array.from(host.children)
    expect(shown(first)).toEqual(['target'])
    expect(first.children).toHaveLength(1)
  })

  it('in the layout editor lets blocks and lines be picked and dragged, and names a block on hover', () => {
    const picked: DragItem[] = []
    const editing: CardLayoutEditing = {
      selection: { kind: 'block', element: 'target' },
      dragged: null,
      startDrag: item => () => { picked.push(item) },
      select: item => { picked.push(item) },
      labelOf: element => `Label ${element}`,
      setRoot: () => {},
    }
    const editedView = view([blocks('target'), { kind: 'divider' }, blocks('translation')])
    act(() => root.render(
      <CardLayoutEditingContext.Provider value={editing}>
        <CardBody view={editedView} columns={shownColumns(editedView, ctx())} detailsOpen={false} onToggleDetails={() => {}} />
      </CardLayoutEditingContext.Provider>,
    ))

    const target = host.querySelector('[data-element="target"]')!
    expect([target.getAttribute('role'), target.getAttribute('aria-pressed'), target.textContent]).toEqual(['button', 'true', 'glareLabel target'])
    const line = host.querySelector('hr')!
    act(() => { line.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })) })
    act(() => { target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
    expect(picked).toEqual([{ kind: 'divider', column: 0, row: 1 }, { kind: 'block', element: 'target', placed: true }])
  })

  it('on the review is a plain card: nothing to pick or drag', () => {
    render(view([blocks('target'), { kind: 'divider' }, blocks('translation')]))
    expect([host.querySelector('[role="button"][data-element]'), host.querySelector('hr')?.getAttribute('role')]).toEqual([null, null])
  })
})
