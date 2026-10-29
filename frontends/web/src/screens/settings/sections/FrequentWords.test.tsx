import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FrequentWordThresholdOption, Settings } from '@/api/types'
import { FrequentWords } from './Words'
import type { SettingsStore } from '../useSettings'

const THRESHOLDS: FrequentWordThresholdOption[] = [
  { value: '4.5', zipf: 4.5, examples: ['concept', 'classic', 'assume', 'weird'] },
  { value: 'off', zipf: null, examples: [] },
]

describe('Frequent words', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    root = createRoot(host)
  })

  afterEach(() => act(() => root.unmount()))

  const render = (change = vi.fn()) => {
    const store = { frequentWordThresholds: THRESHOLDS, change } as unknown as SettingsStore
    const form = { frequent_word_threshold: '4.5' } as unknown as Settings
    act(() => root.render(<FrequentWords store={store} form={form} />))
    return change
  }
  const choices = () => [...host.querySelectorAll('label')]

  it('shows each example word on its own instead of one joined line', () => {
    render()

    const [words, off] = choices()
    expect([...words.querySelectorAll('span span')].map(tag => tag.textContent)).toEqual(['concept', 'classic', 'assume', 'weird'])
    expect(words.textContent).not.toContain(',')
    expect(words.textContent).not.toContain('4.5')
    expect(off.textContent).toContain('Off')
  })

  it('marks the saved value and changes it on a click', () => {
    const change = render()

    expect(choices().map(choice => choice.querySelector('input')!.checked)).toEqual([true, false])
    act(() => choices()[1].querySelector('input')!.click())
    expect(change).toHaveBeenCalledWith('frequent_word_threshold', 'off')
  })
})
