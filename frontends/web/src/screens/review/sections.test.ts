import { describe, expect, it } from 'vitest'
import type { CandidateSection, StoredCandidate } from '@/api/types'
import { withSectionLabels } from './sections'

const card = (id: number, section: CandidateSection) => ({ id, section }) as StoredCandidate

describe('withSectionLabels', () => {
  it('labels each section after ready before its first card', () => {
    const items = withSectionLabels([card(1, 'ready'), card(2, 'extra'), card(3, 'extra'), card(4, 'probably_known')])
    expect(items.map(item => (item.kind === 'section' ? item.section : item.candidate.id))).toEqual(
      [1, 'extra', 2, 3, 'probably_known', 4],
    )
  })

  it('labels extra at the top when nothing is ready', () => {
    const items = withSectionLabels([card(2, 'extra')])
    expect(items[0]).toEqual({ kind: 'section', section: 'extra' })
  })
})
