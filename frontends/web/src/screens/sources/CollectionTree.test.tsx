import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionNode, CollectionTree as Tree } from '@/api/types'
import { COLLECTION_MIME, CollectionTree } from './CollectionTree'

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

  const ROW_HEIGHT = 40
  const transfer = () => {
    const data = new Map<string, string>()
    return {
      get types() { return [...data.keys()] },
      setData: (type: string, value: string) => { data.set(type, value) },
      getData: (type: string) => data.get(type) ?? '',
    }
  }
  const drag = (el: HTMLElement, type: string, dataTransfer: ReturnType<typeof transfer>, extra: { clientY?: number; relatedTarget?: EventTarget | null } = {}) => {
    el.getBoundingClientRect = () => ({ top: 0, height: ROW_HEIGHT } as DOMRect)
    const event = new Event(type, { bubbles: true, cancelable: true })
    Object.assign(event, { dataTransfer, clientY: extra.clientY ?? ROW_HEIGHT / 2, relatedTarget: extra.relatedTarget ?? null })
    act(() => { el.dispatchEvent(event) })
  }

  it('drops a collection inside a node even right after the drag left it', () => {
    const data = transfer()
    drag(item('Nested'), 'dragstart', data)
    drag(item('Top'), 'dragover', data)
    drag(item('Top'), 'dragleave', data)
    drag(item('Top'), 'drop', data)
    expect(data.types).toEqual([COLLECTION_MIME])
    expect(handlers.onMove).toHaveBeenCalledWith(2, 1, 0)
  })

  it('keeps the drop highlight while the cursor moves onto the row text', () => {
    const data = transfer()
    drag(item('Nested'), 'dragstart', data)
    drag(item('Top'), 'dragover', data)
    const name = item('Top').querySelector('span:nth-of-type(2)')!
    drag(item('Top'), 'dragleave', data, { relatedTarget: name })
    expect(item('Top').className).toMatch(/inside/)
    drag(item('Top'), 'dragleave', data)
    expect(item('Top').className).not.toMatch(/inside/)
  })

  const remountWithChild = (collapsed: boolean) => {
    const child = { ...node(3, 'Child', false), parent_id: 1 }
    const parent = { ...node(1, 'Top', true), children: [child] }
    localStorage.setItem('sources.collapsedCollections', JSON.stringify(collapsed ? [1] : []))
    act(() => root.unmount())
    root = createRoot(host)
    act(() => root.render(<CollectionTree tree={{ ...tree, collections: [parent] }} scope="all" draggable {...handlers} />))
  }
  const openMenu = (name: string) => act(() => {
    item(name).dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }))
  })
  const menuItem = (label: string) =>
    [...document.querySelectorAll<HTMLElement>('[role="menuitem"]')].find(el => el.textContent?.includes(label))!

  it('expands a collapsed parent when a subcollection is started in it', () => {
    remountWithChild(true)
    expect(host.textContent).not.toContain('Child')
    openMenu('Top')
    act(() => menuItem('New subcollection').click())
    expect(host.textContent).toContain('Child')
    expect(host.querySelector('input')).not.toBeNull()
    localStorage.clear()
  })

  it('twisty double click and Enter neither rename nor select the node', () => {
    remountWithChild(false)
    const twisty = host.querySelector<HTMLButtonElement>('[aria-label="Collapse"]')!
    act(() => { twisty.dispatchEvent(new MouseEvent('dblclick', { bubbles: true })) })
    press(twisty, 'Enter')
    expect(host.querySelector('input')).toBeNull()
    expect(handlers.onSelect).not.toHaveBeenCalled()
    localStorage.clear()
  })

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
    openMenu('Top')
    expect(host.textContent).toContain('New subcollection')
    act(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })))
    openMenu('Nested')
    expect(host.textContent).not.toContain('New subcollection')
  })
})
