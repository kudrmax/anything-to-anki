import { describe, expect, it } from 'vitest'
import { resolveTheme, themeStore } from './theme'

describe('resolveTheme', () => {
  it('returns the explicit choice', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })
  it('follows the system when set to system', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
  })
})

describe('themeStore', () => {
  it('shares one preference between all subscribers', () => {
    const seen: string[] = []
    const unsubscribe = themeStore.subscribe(() => seen.push(themeStore.getSnapshot()))
    themeStore.set('system')
    themeStore.set('light')
    unsubscribe()
    themeStore.set('dark')
    expect(seen).toEqual(['system', 'light'])
    expect(themeStore.getSnapshot()).toBe('dark')
  })
})
