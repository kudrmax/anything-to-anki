import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionNode, CollectionTree } from '@/api/types'
import { MoveToModal } from './MoveToModal'

const counts = { total: 1, reviewed: 0, pending: 1, progress: { decided: 0, total: 0 } }
const node = (id: number, name: string, parentId: number | null, depth: number, moveTargets: (number | null)[], children: CollectionNode[] = []): CollectionNode => ({
  id, name, parent_id: parentId, counts, depth, accepts_collections: true, move_targets: moveTargets, children,
})
// Friends › Season 1 › Episodes › Ep 1; Season 2; Podcasts. Цели переноса задаёт backend.
const tree: CollectionTree = {
  all: counts,
  unsorted: counts,
  max_depth: 4,
  collections: [
    node(1, 'Friends', null, 1, [null, 2], [
      node(11, 'Season 1', 1, 2, [null, 1, 12, 2], [
        node(111, 'Episodes', 11, 3, [null, 1, 11, 12, 2], [
          node(1111, 'Ep 1', 111, 4, [null, 1, 11, 111, 12, 2]),
        ]),
      ]),
      node(12, 'Season 2', 1, 2, [null, 1, 11, 111, 2]),
    ]),
    node(2, 'Podcasts', null, 1, [null, 1, 11, 111, 12]),
  ],
}

describe('MoveToModal', () => {
  let root: Root
  const onPick = vi.fn()
  const onClose = vi.fn()

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onPick.mockReset()
    onClose.mockReset()
    root = createRoot(document.createElement('div'))
  })

  afterEach(() => act(() => root.unmount()))

  const render = (props: { excludeId?: number; collectionsOnly?: boolean } = {}) =>
    act(() => root.render(<MoveToModal tree={tree} title="Move to" onPick={onPick} onClose={onClose} {...props} />))
  const input = () => document.body.querySelector<HTMLInputElement>('[role="combobox"]')!
  const options = () => [...document.body.querySelectorAll<HTMLButtonElement>('[role="option"]')]
  const labels = () => options().map(o => o.textContent)
  const typeInto = (value: string) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
    act(() => {
      setter.call(input(), value)
      input().dispatchEvent(new Event('input', { bubbles: true }))
    })
  }
  const press = (key: string) => act(() => { input().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true })) })

  it('offers Unsorted and every node of every level for sources', () => {
    render()
    expect(labels()).toEqual(['Unsorted', 'Friends', 'Season 1', 'Episodes', 'Ep 1', 'Season 2', 'Podcasts'])
  })

  it('indents options by depth and drops the indent while searching', () => {
    render()
    const indents = () => options().map(o => o.style.getPropertyValue('--indent'))
    expect(indents()).toEqual(['0', '0', '1', '2', '3', '1', '0'])
    typeInto('ep')
    expect(labels()).toEqual(['Friends / Season 1 / Episodes', 'Friends / Season 1 / Episodes / Ep 1'])
    expect(indents()).toEqual(['0', '0'])
  })

  it('focuses the search', () => {
    render()
    expect(document.activeElement).toBe(input())
  })

  it('filters by search and Enter picks the first match', () => {
    render()
    typeInto('season')
    expect(labels()).toEqual(['Friends / Season 1', 'Friends / Season 2'])
    press('Enter')
    expect(onPick).toHaveBeenCalledWith(11, 'Season 1')
  })

  it('arrow keys move the highlight before Enter', () => {
    render()
    press('ArrowDown')
    press('ArrowDown')
    press('Enter')
    expect(onPick).toHaveBeenCalledWith(11, 'Season 1')
  })

  it('picks Unsorted as null', () => {
    render()
    act(() => options()[0].click())
    expect(onPick).toHaveBeenCalledWith(null, 'Unsorted')
  })

  it('enables exactly the move targets the backend listed', () => {
    render({ collectionsOnly: true, excludeId: 12 })
    expect(labels()).toEqual(['Top level', 'Friends' + 'Current', 'Season 1', 'Episodes', 'Ep 1', 'Podcasts'])
    const enabled = options().filter(o => !o.disabled).map(o => o.textContent)
    expect(enabled).toEqual(['Top level', 'Friends' + 'Current', 'Season 1', 'Episodes', 'Podcasts'])
    expect(document.body.textContent).toContain('Collections nest at most 4 levels deep.')
    press('Enter')
    expect(onPick).toHaveBeenCalledWith(null, 'Top level')
  })

  it('hides the moving collection with its whole subtree', () => {
    render({ collectionsOnly: true, excludeId: 11 })
    expect(labels()).toEqual(['Top level', 'Friends' + 'Current', 'Season 2', 'Podcasts'])
  })

  it('skips disabled targets with the keyboard', () => {
    render({ collectionsOnly: true, excludeId: 1 })
    expect(labels()).toEqual(['Top level' + 'Current', 'Podcasts'])
    const [top, podcasts] = options()
    expect(top.disabled).toBe(false)
    expect(podcasts.disabled).toBe(false)
    render({ collectionsOnly: true, excludeId: 2 })
    expect(options().filter(o => o.disabled).map(o => o.textContent)).toEqual(['Ep 1'])
    press('ArrowDown')
    press('ArrowDown')
    press('ArrowDown')
    press('ArrowDown')
    press('Enter')
    expect(onPick).toHaveBeenCalledWith(12, 'Season 2')
  })

  it('Escape closes', () => {
    render()
    press('Escape')
    expect(onClose).toHaveBeenCalled()
  })

  it('picking the current parent of a collection just closes', () => {
    render({ excludeId: 11, collectionsOnly: true })
    const current = options().find(o => o.textContent?.includes('Current'))!
    expect(current.textContent).toContain('Friends')
    act(() => current.click())
    expect(onPick).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
