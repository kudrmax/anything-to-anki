import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionNode } from '@/api/types'
import { ScopeHeader } from './ScopeHeader'

const counts = { total: 2, reviewed: 1, pending: 0, candidate_count: 0, decided_count: 0 }
const node = (id: number, name: string, depth: number): CollectionNode => ({
  id, name, parent_id: depth === 1 ? null : id - 1, counts, depth, accepts_collections: true, move_targets: [null], children: [],
})
const [a, b, c, d] = [node(1, 'A', 1), node(2, 'B', 2), node(3, 'C', 3), node(4, 'D', 4)]

describe('ScopeHeader', () => {
  let host: HTMLDivElement
  let root: Root
  const onOpenAncestor = vi.fn()
  const noop = () => {}

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onOpenAncestor.mockReset()
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  const render = (ancestors: CollectionNode[], current: CollectionNode) => act(() => root.render(
    <ScopeHeader
      title={current.name} ancestors={ancestors} counts={counts} node={current} processing={false}
      onOpenAncestor={onOpenAncestor} onProcessAll={noop} onExport={noop}
      onRename={noop} onNewSubcollection={noop} onMoveTo={noop} onDelete={noop}
    />,
  ))
  const title = () => host.querySelector('h1')!
  const links = () => [...title().querySelectorAll('button')].map(el => el.textContent)

  it('folds the middle of a long path: A › … › C › D', () => {
    render([a, b, c], d)
    expect(title().textContent).toBe('A…CD')
    expect(links()).toEqual(['A', 'C'])
    expect(title().querySelectorAll('svg')).toHaveLength(3)
    const gap = [...title().querySelectorAll('span')].find(el => el.textContent === '…')!
    expect(gap.getAttribute('title')).toBe('B')
    expect(gap.closest('button')).toBeNull()
  })

  it('opens an ancestor on click', () => {
    render([a, b, c], d)
    act(() => title().querySelector('button')!.click())
    expect(onOpenAncestor).toHaveBeenCalledWith(1)
  })

  it('shows a short path in full', () => {
    render([a, b], c)
    expect(title().textContent).toBe('ABC')
    expect(links()).toEqual(['A', 'B'])
  })

  it('shows only the name at the top level', () => {
    render([], a)
    expect(title().textContent).toBe('A')
    expect(links()).toEqual([])
  })
})
