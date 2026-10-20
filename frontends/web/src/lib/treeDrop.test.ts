import { describe, expect, it } from 'vitest'
import type { CollectionNode } from '@/api/types'
import { collectionDrop, zoneAt } from './treeDrop'

const counts = { total: 0, reviewed: 0, pending: 0, progress: { decided: 0, total: 0 }, status: 'new' as const, can_process: false, can_review: false, review_fraction: 0, progress_caption: '' }

/** move_targets задаются явно: их считает backend, фронт лишь сверяется с ними. */
const node = (id: number, parent: number | null, depth: number, moveTargets: (number | null)[], children: CollectionNode[] = []): CollectionNode => ({
  id, name: `c${id}`, parent_id: parent, counts, depth, accepts_collections: depth < 4, move_targets: moveTargets, children,
})

// 1 › 2 › 3 › 4, затем 5 и 6 на верхнем уровне.
const TREE = [
  node(1, null, 1, [null, 5, 6], [
    node(2, 1, 2, [null, 1, 5, 6], [
      node(3, 2, 3, [null, 1, 2, 5, 6], [
        node(4, 3, 4, [null, 1, 2, 3, 5, 6]),
      ]),
    ]),
  ]),
  node(5, null, 1, [null, 1, 2, 3, 6]),
  node(6, null, 1, [null, 1, 2, 3, 4, 5]),
]

describe('collectionDrop', () => {
  it('reorders among top level', () => {
    expect(collectionDrop(TREE, 5, 1, 'before')).toEqual({ parentId: null, position: 0 })
    expect(collectionDrop(TREE, 1, 6, 'after')).toEqual({ parentId: null, position: 2 })
  })
  it('nests a collection at the end of the target', () => {
    expect(collectionDrop(TREE, 5, 1, 'inside')).toEqual({ parentId: 1, position: 1 })
    expect(collectionDrop(TREE, 6, 4, 'inside')).toEqual({ parentId: 4, position: 0 })
  })
  it('places a collection next to a deep sibling', () => {
    expect(collectionDrop(TREE, 6, 4, 'before')).toEqual({ parentId: 3, position: 0 })
    expect(collectionDrop(TREE, 5, 3, 'after')).toEqual({ parentId: 2, position: 1 })
  })
  it('lifts a deep subcollection to the top level', () => {
    expect(collectionDrop(TREE, 4, 5, 'after')).toEqual({ parentId: null, position: 2 })
  })
  it('keeps the position among current siblings without the dragged one', () => {
    expect(collectionDrop(TREE, 3, 2, 'inside')).toEqual({ parentId: 2, position: 0 })
  })
  it('refuses parents the backend did not list', () => {
    expect(collectionDrop(TREE, 2, 3, 'inside')).toBeNull()
    expect(collectionDrop(TREE, 2, 4, 'inside')).toBeNull()
    expect(collectionDrop(TREE, 2, 4, 'before')).toBeNull()
    expect(collectionDrop(TREE, 5, 4, 'inside')).toBeNull()
    expect(collectionDrop(TREE, 1, 3, 'after')).toBeNull()
  })
  it('never drops a collection onto itself', () => {
    expect(collectionDrop(TREE, 6, 6, 'inside')).toBeNull()
    expect(collectionDrop(TREE, 6, 6, 'before')).toBeNull()
  })
})

describe('zoneAt', () => {
  it('splits a row in three when nesting is possible', () => {
    expect(zoneAt(1, 40, true)).toBe('before')
    expect(zoneAt(20, 40, true)).toBe('inside')
    expect(zoneAt(39, 40, true)).toBe('after')
    expect(zoneAt(19, 40, false)).toBe('before')
    expect(zoneAt(21, 40, false)).toBe('after')
  })
})
