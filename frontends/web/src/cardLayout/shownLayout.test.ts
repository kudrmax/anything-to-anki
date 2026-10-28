import { describe, expect, it } from 'vitest'
import type { CardElement, CardLayoutRow, CardLayoutView } from '@/api/types'
import { reviewCard } from '@/screens/review/reviewFixtures'
import type { CardBlockContext } from './CardBlockContext'
import { shownColumns } from './shownLayout'

const STYLE = { size: 'm', tone: 'primary', bold: false, align: 'start', valign: 'baseline', space_top: 'none', space_right: 'none', space_bottom: 'none', space_left: 'none' } as const
const ELEMENTS: CardElement[] = ['target', 'translation', 'picture', 'synonyms']
const DIVIDER: CardLayoutRow = { kind: 'divider', sticks: 'below' }
const blocks = (...elements: CardElement[]): CardLayoutRow => ({ kind: 'blocks', elements })

const view = (...columns: CardLayoutRow[][]): CardLayoutView => ({
  layout: {
    columns: columns.map(rows => ({ width: 'normal', rows })),
    // Перевод прижат к низу колонки.
    styles: ELEMENTS.map(element => ({ element, style: element === 'translation' ? { ...STYLE, valign: 'bottom' } : STYLE })),
  },
  elements: ELEMENTS.map(element => ({ element, kind: 'text', can_hide: true })),
  hidden: [],
  can_add_column: true,
  can_remove_column: true,
})

// У карточки есть слово и перевод; картинки и синонимов нет.
const ctx: CardBlockContext = {
  candidate: reviewCard({
    lemma: 'glare',
    meaning: { meaning: null, translation: 'сердито смотреть', synonyms: null, examples: null, ipa: null, status: 'done', error: null, generated_at: null },
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
}

const kinds = (layout: CardLayoutView, keepEmpty = false) =>
  shownColumns(layout, ctx, keepEmpty).map(column => [column.index, column.rows.map(row => (row.kind === 'divider' ? '---' : row.blocks.map(b => b.element).join('+')))])

describe('shownColumns', () => {
  it('merges lines left next to each other by empty rows into one', () => {
    expect(kinds(view([blocks('target'), DIVIDER, blocks('picture'), DIVIDER, blocks('translation')]))).toEqual([[0, ['target', '---', 'translation']]])
  })

  it('draws no line at the top or the bottom of a column', () => {
    expect(kinds(view([DIVIDER, blocks('target'), DIVIDER, blocks('synonyms'), DIVIDER]))).toEqual([[0, ['target']]])
  })

  it('leaves out a column with nothing to show, unless empty columns are wanted', () => {
    const layout = view([blocks('target')], [blocks('picture', 'synonyms'), DIVIDER], [blocks('translation')])
    expect(kinds(layout)).toEqual([[0, ['target']], [2, ['translation']]])
    expect(kinds(layout, true)).toEqual([[0, ['target']], [1, []], [2, ['translation']]])
  })

  it('keeps the first column of a card with nothing to show', () => {
    expect(kinds(view([blocks('picture')], [blocks('synonyms')]))).toEqual([[0, []]])
  })

  it('pushes everything from the first Bottom block, with the line right above it, to the column bottom', () => {
    const [withLine] = shownColumns(view([blocks('target'), DIVIDER, blocks('translation')]), ctx)
    expect(withLine.bottomFrom).toBe(1)
    const [noLine] = shownColumns(view([blocks('target'), blocks('translation'), blocks('synonyms')]), ctx)
    expect(noLine.bottomFrom).toBe(1)
    const [none] = shownColumns(view([blocks('target')]), ctx)
    expect(none.bottomFrom).toBeNull()
  })

  it('leaves a line that sticks to the row above where it is: only the rows below go down', () => {
    const [column] = shownColumns(view([blocks('target'), { kind: 'divider', sticks: 'above' }, blocks('translation')]), ctx)
    expect(column.bottomFrom).toBe(2)
  })
})
