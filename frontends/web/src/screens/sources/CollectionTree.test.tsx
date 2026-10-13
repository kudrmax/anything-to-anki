import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionNode, CollectionTree as Tree } from '@/api/types'
import { CollectionTree } from './CollectionTree'

const counts = { total: 1, reviewed: 0, pending: 1 }
const node = (id: number, name: string, accepts: boolean): CollectionNode => ({
  id, name, parent_id: null, counts, accepts_collections: accepts, can_be_nested: !accepts, children: [],
})
const tree: Tree = {
  all: counts,
  unsorted: counts,
  collections: [node(1, 'Top', true), node(2, 'Nested', false)],
}

describe('CollectionTree', () => {
  let host: HTMLDivElement
  let root: Root
  const handlers = {
    onSelect: vi.fn(), onCreate: vi.fn(), onRename: vi.fn(), onMove: vi.fn(),
    onDelete: vi.fn(), onMoveTo: vi.fn(), onDropSources: vi.fn(),
  }

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    Object.values(handlers).forEach(h => h.mockReset())
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
    act(() => root.render(<CollectionTree tree={tree} scope="all" draggable {...handlers} />))
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  const item = (name: string) => [...host.querySelectorAll<HTMLElement>('[role="treeitem"]')].find(el => el.textContent?.includes(name))!

  const typeInto = (input: HTMLInputElement, value: string) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
    act(() => {
      setter.call(input, value)
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }
  const press = (el: HTMLElement, key: string) =>
    act(() => { el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true })) })

  it('selects a node on click', () => {
    act(() => item('Top').click())
    expect(handlers.onSelect).toHaveBeenCalledWith(1)
  })

  it('creates a collection once on Enter', () => {
    act(() => host.querySelector<HTMLButtonElement>('[aria-label="New collection"]')!.click())
    const input = host.querySelector('input')!
    typeInto(input, 'Fresh')
    press(input, 'Enter')
    expect(handlers.onCreate).toHaveBeenCalledTimes(1)
    expect(handlers.onCreate).toHaveBeenCalledWith('Fresh', null)
  })

  it('renames on F2 then Enter', () => {
    press(item('Top'), 'F2')
    const input = host.querySelector('input')!
    typeInto(input, 'Renamed')
    press(input, 'Enter')
    expect(handlers.onRename).toHaveBeenCalledTimes(1)
    expect(handlers.onRename).toHaveBeenCalledWith(1, 'Renamed')
  })

  it('offers New subcollection only for nodes that accept collections', () => {
    const openMenu = (name: string) => act(() => {
      item(name).dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }))
    })
    openMenu('Top')
    expect(host.textContent).toContain('New subcollection')
    act(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })))
    openMenu('Nested')
    expect(host.textContent).not.toContain('New subcollection')
  })
})
