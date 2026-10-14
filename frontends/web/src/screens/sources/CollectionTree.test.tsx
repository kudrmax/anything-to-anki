import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionNode, CollectionTree as Tree } from '@/api/types'
import { COLLECTION_MIME, CollectionTree } from './CollectionTree'

const counts = { total: 1, reviewed: 0, pending: 1, candidate_count: 0, decided_count: 0 }
const node = (id: number, name: string, accepts: boolean, moveTargets: (number | null)[] = [null]): CollectionNode => ({
  id, name, parent_id: null, counts, depth: 1, accepts_collections: accepts, move_targets: moveTargets, children: [],
})
const tree: Tree = {
  all: counts,
  unsorted: counts,
  max_depth: 5,
  collections: [node(1, 'Top', true), node(2, 'Nested', false, [null, 1])],
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
    const child = { ...node(3, 'Child', false, [null, 1]), parent_id: 1, depth: 2 }
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

  it('renames in place of the name: subcollections stay, Escape keeps the old name', () => {
    remountWithChild(false)
    press(item('Top'), 'F2')
    const input = host.querySelector('input')!
    const cells = [...input.parentElement!.children]
    expect(cells.indexOf(input)).toBe(cells.length - 2)
    expect(host.textContent).toContain('Child')
    typeInto(input, 'Changed')
    press(input, 'Escape')
    expect(handlers.onRename).not.toHaveBeenCalled()
    expect(host.querySelector('input')).toBeNull()
    localStorage.clear()
  })

  it('renders every level of a deep tree with a guide and its aria-level', () => {
    const level4 = { ...node(4, 'Level 4', false), parent_id: 3, depth: 4 }
    const level3 = { ...node(3, 'Level 3', true), parent_id: 2, depth: 3, children: [level4] }
    const level2 = { ...node(2, 'Level 2', true), parent_id: 1, depth: 2, children: [level3] }
    const level1 = { ...node(1, 'Level 1', true), children: [level2] }
    act(() => root.render(<CollectionTree tree={{ ...tree, collections: [level1] }} scope="all" draggable {...handlers} />))
    expect([1, 2, 3, 4].map(n => item(`Level ${n}`).getAttribute('aria-level'))).toEqual(['1', '2', '3', '4'])
    const groups = [...host.querySelectorAll('[role="group"]')]
    expect(groups).toHaveLength(3)
    expect(groups[0].contains(groups[1]) && groups[1].contains(groups[2])).toBe(true)
    expect(groups[2].contains(item('Level 4'))).toBe(true)
    expect(item('Level 3').querySelector('[aria-label="Collapse"]')).not.toBeNull()
    expect(item('Level 4').querySelector('[aria-label="Collapse"]')).toBeNull()
  })

  it('creates a subcollection deep in the tree', () => {
    const level3 = { ...node(3, 'Level 3', true), parent_id: 2, depth: 3 }
    const level2 = { ...node(2, 'Level 2', true), parent_id: 1, depth: 2, children: [level3] }
    act(() => root.render(<CollectionTree tree={{ ...tree, collections: [{ ...node(1, 'Level 1', true), children: [level2] }] }} scope="all" draggable {...handlers} />))
    act(() => item('Level 3').querySelector<HTMLButtonElement>('[aria-label="New subcollection"]')!.click())
    const input = host.querySelector('input')!
    expect(host.querySelectorAll('[role="group"]')).toHaveLength(3)
    typeInto(input, 'Level 4')
    press(input, 'Enter')
    expect(handlers.onCreate).toHaveBeenCalledWith('Level 4', 3)
  })

  it('shows the hover + only on nodes that accept collections', () => {
    expect(item('Top').querySelector('[aria-label="New subcollection"]')).not.toBeNull()
    expect(item('Nested').querySelector('[aria-label="New subcollection"]')).toBeNull()
  })

  it('refuses a drop on a parent the backend did not list', () => {
    const child = { ...node(3, 'Child', false, [1]), parent_id: 1, depth: 2 }
    act(() => root.render(<CollectionTree tree={{ ...tree, collections: [{ ...node(1, 'Top', true), children: [child] }, node(2, 'Nested', true)] }} scope="all" draggable {...handlers} />))
    const data = transfer()
    drag(item('Child'), 'dragstart', data)
    for (const clientY of [1, ROW_HEIGHT / 2, ROW_HEIGHT - 1]) {
      drag(item('Nested'), 'dragover', data, { clientY })
      expect(item('Nested').className).not.toMatch(/inside|before|after/)
    }
    drag(item('Nested'), 'drop', data)
    expect(handlers.onMove).not.toHaveBeenCalled()
  })

  it('offers New subcollection only for nodes that accept collections', () => {
    openMenu('Top')
    expect(host.textContent).toContain('New subcollection')
    act(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })))
    openMenu('Nested')
    expect(host.textContent).not.toContain('New subcollection')
  })

  it('shows the decision progress of a collection and only the source count without candidates', () => {
    const progressed = { ...node(3, 'Books', true), counts: { ...counts, total: 2, candidate_count: 1070, decided_count: 41 } }
    act(() => root.render(<CollectionTree tree={{ ...tree, collections: [progressed] }} scope="all" draggable {...handlers} />))

    expect(item('Books').textContent).toContain('4%')
    expect(item('Books').querySelector('[title="41 of 1070 decided · 2 sources"]')).not.toBeNull()
    expect(item('All').textContent).not.toContain('%')
  })
})
