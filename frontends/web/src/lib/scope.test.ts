import { describe, expect, it } from 'vitest'
import { parseScope, parseSetScope, parseView, reviewPath, scopeQuery, sourceScope, viewPath } from './scope'

describe('parseScope', () => {
  it('reads all, unsorted and ids', () => {
    expect(parseScope(null)).toBe('all')
    expect(parseScope('unsorted')).toBe('unsorted')
    expect(parseScope('12')).toBe(12)
  })
  it('falls back to all on garbage', () => {
    expect(parseScope('-3')).toBe('all')
    expect(parseScope('abc')).toBe('all')
  })
})

describe('parseView', () => {
  it('opens Recent without a scope and the named scope otherwise', () => {
    expect(parseView(null)).toBe('recent')
    expect(parseView('all')).toBe('all')
    expect(parseView('unsorted')).toBe('unsorted')
    expect(parseView('12')).toBe(12)
  })
})

describe('viewPath', () => {
  it('names every scope and leaves Recent bare', () => {
    expect(viewPath('recent')).toBe('/')
    expect(viewPath('all')).toBe('/?scope=all')
    expect(viewPath(12)).toBe('/?scope=12')
  })
})

describe('scopeQuery', () => {
  it('omits all and keeps the rest', () => {
    expect(scopeQuery('all')).toBe('')
    expect(scopeQuery('unsorted')).toBe('?scope=unsorted')
    expect(scopeQuery(12)).toBe('?scope=12')
  })
})

describe('parseSetScope', () => {
  it('keeps source tokens apart from collections', () => {
    expect(parseSetScope('source-7')).toBe('source-7')
    expect(parseSetScope('7')).toBe(7)
    expect(parseScope('source-7')).toBe('all')
  })
  it('reads all and unsorted like a scope, and garbage as all', () => {
    expect(parseSetScope(null)).toBe('all')
    expect(parseSetScope('unsorted')).toBe('unsorted')
    expect(parseSetScope('source-')).toBe('all')
    expect(parseSetScope('source-7x')).toBe('all')
  })
})

describe('reviewPath', () => {
  it('builds one review path for every scope', () => {
    expect(reviewPath('all')).toBe('/review')
    expect(reviewPath(12)).toBe('/review?scope=12')
    expect(reviewPath(sourceScope(7), 3)).toBe('/review?scope=source-7&candidate=3')
    expect(reviewPath('all', 3)).toBe('/review?candidate=3')
  })
})
