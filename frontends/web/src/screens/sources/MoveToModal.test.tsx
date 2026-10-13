import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionNode, CollectionTree } from '@/api/types'
import { MoveToModal } from './MoveToModal'

const counts = { total: 1, reviewed: 0, pending: 1 }
const node = (id: number, name: string, parentId: number | null, children: CollectionNode[] = []): CollectionNode => ({
  id, name, parent_id: parentId, counts, accepts_collections: parentId === null, can_be_nested: children.length === 0, children,
})
const tree: CollectionTree = {
  all: counts,
  unsorted: counts,
  collections: [
    node(1, 'Friends', null, [node(11, 'Season 1', 1), node(12, 'Season 2', 1)]),
    node(2, 'Podcasts', null),
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

  it('offers Unsorted and every node for sources', () => {
    render()
    expect(labels()).toEqual(['Unsorted', 'Friends', 'Season 1', 'Season 2', 'Podcasts'])
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

  it('offers Top level and collections that accept collections when moving a collection', () => {
    render({ collectionsOnly: true, excludeId: 12 })
    expect(labels()).toEqual(['Top level', 'Friends' + 'Current', 'Podcasts'])
    press('Enter')
    expect(onPick).toHaveBeenCalledWith(null, 'Top level')
  })

  it('hides the moving collection itself', () => {
    render({ collectionsOnly: true, excludeId: 2 })
    expect(labels()).toEqual(['Top level' + 'Current', 'Friends'])
  })

  it('keeps a collection with subcollections at the top level', () => {
    render({ collectionsOnly: true, excludeId: 1 })
    const [top, podcasts] = options()
    expect(top.disabled).toBe(false)
    expect(podcasts.disabled).toBe(true)
    press('ArrowDown')
    press('Enter')
    expect(onPick).toHaveBeenCalledWith(null, 'Top level')
  })

  it('Escape closes', () => {
    render()
    press('Escape')
    expect(onClose).toHaveBeenCalled()
  })
})
