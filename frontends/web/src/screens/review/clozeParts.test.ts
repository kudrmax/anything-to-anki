import { describe, expect, it } from 'vitest'
import { clozeParts } from './clozeParts'

const plain = (text: string) => ({ text, bold: false, target: false })
const target = (text: string) => ({ text, bold: false, target: true })

describe('clozeParts', () => {
  it('marks the saved hidden words by their index in the phrase', () => {
    const parts = clozeParts([plain('She finally '), target('gave'), plain(' up smoking.')], [3])
    expect(parts).toEqual([
      { text: 'She finally ', target: false, hidden: false },
      { text: 'gave', target: true, hidden: false },
      { text: ' ', target: false, hidden: false },
      { text: 'up', target: false, hidden: true },
      { text: ' smoking.', target: false, hidden: false },
    ])
  })
  it('keeps a hidden word whole when the target is only part of it', () => {
    const parts = clozeParts([plain('He '), target('accused'), plain(', of course.')], [1])
    expect(parts.filter(p => p.hidden).map(p => p.text)).toEqual(['accused', ','])
  })
})
