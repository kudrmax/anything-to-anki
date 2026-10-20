import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionNode, ScopeCounts } from '@/api/types'
import { ScopeHeader } from './ScopeHeader'

const counts: ScopeCounts = {
  total: 2, reviewed: 1, pending: 0, progress: { decided: 3, total: 12 },
  status: 'partially_reviewed', can_process: false, can_review: true, review_fraction: 0.25, progress_caption: '3 of 12 phrases',
  available_operations: ['rebuild'], can_start_operation: true, operation_hint: null, can_export: true,
}
const node = (id: number, name: string, depth: number): CollectionNode => ({
  id, name, parent_id: depth === 1 ? null : id - 1, counts, depth, accepts_collections: true, move_targets: [null], children: [],
})
const [a, b, c, d] = [node(1, 'A', 1), node(2, 'B', 2), node(3, 'C', 3), node(4, 'D', 4)]

describe('ScopeHeader', () => {
  let host: HTMLDivElement
  let root: Root
  const onOpenAncestor = vi.fn()
  const onReview = vi.fn()
  const onOperation = vi.fn()
  const noop = () => {}

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onOpenAncestor.mockReset()
    onReview.mockReset()
    onOperation.mockReset()
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  const render = (ancestors: CollectionNode[], current: CollectionNode | null, shown: ScopeCounts | null = counts, processing = false) => act(() => root.render(
    <ScopeHeader
      title={current?.name ?? 'All sources'} ancestors={ancestors} counts={shown} node={current} processing={processing}
      onOpenAncestor={onOpenAncestor} onProcessAll={noop} onReview={onReview} onExport={noop} onOperation={onOperation}
      onRename={noop} onNewSubcollection={noop} onMoveTo={noop} onDelete={noop} viewItems={[]}
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

  const buttons = () => [...host.querySelectorAll('button')].map(el => el.textContent)

  it('offers Continue on a collection and opens its review', () => {
    render([], a)
    expect(host.textContent).toContain('3 of 12 phrases')
    expect(host.innerHTML).toContain('--p: 25%')
    act(() => [...host.querySelectorAll('button')].find(el => el.textContent === 'Continue')!.click())
    expect(onReview).toHaveBeenCalledOnce()
  })

  it('shows one Process button on a new collection', () => {
    render([], a, { ...counts, status: 'new', can_review: false, pending: 2, can_process: true })
    expect(buttons()).toContain('Process')
    expect(buttons()).not.toContain('Process all (2)')
  })

  it('shows the Process button busy while processing starts', () => {
    render([], a, { ...counts, status: 'new', can_review: false, pending: 2, can_process: true }, true)
    const process = [...host.querySelectorAll('button')].find(el => el.textContent?.includes('Process'))!
    expect(process.disabled).toBe(true)
  })

  it.each<[string, ScopeCounts]>([
    ['an empty collection', { ...counts, total: 0, status: 'new', can_review: false }],
    ['a collection being processed', { ...counts, status: 'processing', can_review: false }],
  ])('offers no processing on %s', (_, shown) => {
    render([], a, shown)
    expect(buttons().filter(label => label?.startsWith('Process') || label === 'Retry')).toEqual([])
  })

  it('shows no counts-made actions before the counts load', () => {
    render([], a, null)
    expect(buttons()).toEqual([''])
    expect(host.textContent).not.toContain('No sources yet')
  })

  it('offers Process all next to the review of a processed collection', () => {
    render([], a, { ...counts, pending: 2, can_process: true })
    expect(buttons()).toEqual(expect.arrayContaining(['Continue', 'Process all (2)']))
  })

  it('shows no review button where the backend refuses review', () => {
    render([], a, { ...counts, status: 'done', can_review: false })
    expect(buttons()).not.toContain('Review')
  })

  const trigger = () => host.querySelector<HTMLElement>('[aria-label$="ctions"]')
  const openMenu = () => act(() => trigger()!.click())
  const menuLabels = () => [...host.querySelectorAll<HTMLElement>('[role="menuitem"]')].map(el => el.textContent)

  it('keeps Export in the menu of a collection, with the actions of a source', () => {
    render([], a)
    expect(buttons()).not.toContain('Export')
    openMenu()
    expect(menuLabels()).toEqual(['Export', 'Rename', 'New subcollection', 'Move to…', 'Rebuild…', 'Delete'])
  })

  it('offers All only Export and the operations, and runs them on the whole scope', () => {
    render([], null, { ...counts, available_operations: ['refresh', 'rebuild'] })
    openMenu()
    expect(menuLabels()).toEqual(['Export', 'Refresh…', 'Rebuild…'])
    act(() => [...host.querySelectorAll<HTMLElement>('[role="menuitem"]')].find(el => el.textContent === 'Rebuild…')!.click())
    expect(onOperation).toHaveBeenCalledWith('rebuild')
  })

  it('keeps the place of the menu when a scope offers nothing', () => {
    render([], null, { ...counts, available_operations: [], can_export: false })
    expect(trigger()).toBeNull()
  })
})
