import { describe, expect, it } from 'vitest'
import type { CollectionNode } from '@/api/types'
import { collectionDrop, zoneAt } from './treeDrop'

const counts = { total: 0, reviewed: 0, pending: 0 }
const node = (id: number, parent: number | null, children: CollectionNode[] = []): CollectionNode => ({
  id, name: `c${id}`, parent_id: parent, counts, accepts_collections: parent === null, can_be_nested: children.length === 0, children,
})
const TREE = [node(1, null, [node(2, 1), node(3, 1)]), node(4, null), node(5, null)]

describe('collectionDrop', () => {
  it('reorders among top level', () => {
    expect(collectionDrop(TREE, 5, 1, 'before')).toEqual({ parentId: null, position: 0 })
    expect(collectionDrop(TREE, 1, 5, 'after')).toEqual({ parentId: null, position: 2 })
  })
  it('nests a childless collection', () => {
    expect(collectionDrop(TREE, 4, 1, 'inside')).toEqual({ parentId: 1, position: 2 })
  })
  it('lifts a subcollection to the top level', () => {
    expect(collectionDrop(TREE, 2, 4, 'after')).toEqual({ parentId: null, position: 2 })
  })
  it('refuses what the backend marks impossible', () => {
    expect(collectionDrop(TREE, 1, 4, 'inside')).toBeNull()
    expect(collectionDrop(TREE, 1, 2, 'before')).toBeNull()
    expect(collectionDrop(TREE, 4, 2, 'inside')).toBeNull()
    expect(collectionDrop(TREE, 4, 4, 'inside')).toBeNull()
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
