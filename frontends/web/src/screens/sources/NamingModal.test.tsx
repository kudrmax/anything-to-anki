import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { CollectionNode, CollectionTree, NamingRequired } from '@/api/types'
import { NamingModal } from './NamingModal'

const RENDER_DELAY_MS = 300
const counts = { total: 1, reviewed: 0, pending: 1, progress: { decided: 0, total: 0 }, status: 'new' as const, can_process: true, can_review: false, review_fraction: 0, progress_caption: '', available_operations: [], can_start_operation: true, operation_hint: null, can_export: false }
const node = (id: number, name: string): CollectionNode => ({
  id, name, parent_id: null, counts, depth: 1, accepts_collections: true, move_targets: [null], children: [],
})
const tree: CollectionTree = { all: counts, unsorted: counts, max_depth: 4, collections: [node(1, 'Atomic Habits'), node(2, 'Podcasts')] }
const REQUIRED: NamingRequired = {
  heading: 'Add 2 files',
  items: [
    { label: 'ah-01 v2.txt', own_title: 'ah-01 v2', words: 100 },
    { label: 'chapter two.md', own_title: 'chapter two', words: 200 },
  ],
  default_collection: null,
  default_rule: '{{collection}} ch{{n}}',
  variables: [
    { token: '{{collection}}', label: 'Collection' },
    { token: '{{n}}', label: 'Number' },
    { token: '{{title}}', label: 'Title from file' },
  ],
}

describe('NamingModal', () => {
  let root: Root
  let renderNames: ReturnType<typeof vi.spyOn>
  const onConfirm = vi.fn()

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.useFakeTimers()
    onConfirm.mockReset()
    renderNames = vi.spyOn(api, 'renderNames').mockImplementation((_rule, collection, titles) =>
      Promise.resolve(titles.map((_, i) => `${collection ?? ''} ch${i + 1}`.trim())))
    root = createRoot(document.createElement('div'))
  })

  afterEach(() => {
    act(() => root.unmount())
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  const render = async () => {
    await act(async () => root.render(<NamingModal required={REQUIRED} tree={tree} onCancel={() => {}} onConfirm={onConfirm} />))
    await act(async () => { await vi.advanceTimersByTimeAsync(RENDER_DELAY_MS) })
  }
  const body = () => document.body
  const rows = () => [...body().querySelectorAll<HTMLInputElement>('[data-row] input')].map(input => input.value)
  const button = (label: string) => [...body().querySelectorAll('button')].find(b => b.textContent?.trim() === label)!
  const collectionField = () => body().querySelector<HTMLInputElement>('[role="combobox"]')!
  const options = () => [...body().querySelectorAll('[role="option"]')].map(o => o.textContent)
  const setValue = (input: HTMLInputElement, value: string) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }

  it('shows each file turning into its title', async () => {
    await render()

    expect(body().textContent).toContain('Add 2 files')
    expect(body().textContent).toContain('ah-01 v2.txt')
    expect(rows()).toEqual(['ch1', 'ch2'])
    expect(renderNames).toHaveBeenCalledWith('{{collection}} ch{{n}}', null, ['ah-01 v2', 'chapter two'], expect.anything())
  })

  it('offers existing collections, a new one by the typed name and none', async () => {
    await render()

    await act(async () => { collectionField().focus(); setValue(collectionField(), 'Atom') })

    expect(options()).toEqual(['No collection', 'Atomic Habits', 'Create «Atom»'])
  })

  it('renders titles with the picked collection', async () => {
    await render()
    await act(async () => { collectionField().focus(); setValue(collectionField(), 'Atom') })
    await act(async () => button('Atomic Habits').click())
    await act(async () => { await vi.advanceTimersByTimeAsync(RENDER_DELAY_MS) })

    expect(rows()).toEqual(['Atomic Habits ch1', 'Atomic Habits ch2'])
  })

  it('sends the collection, the rule and the rows edited by hand', async () => {
    await render()
    await act(async () => { collectionField().focus(); setValue(collectionField(), 'Dune') })
    await act(async () => button('Create «Dune»').click())
    await act(async () => setValue(body().querySelectorAll<HTMLInputElement>('[data-row] input')[1], 'Intro'))
    await act(async () => button('Add').click())

    expect(onConfirm).toHaveBeenCalledWith({
      collection: { existing_id: null, new_name: 'Dune' },
      rule: '{{collection}} ch{{n}}',
      titles: { 1: 'Intro' },
    })
  })

  it('brings an edited row back to the rule', async () => {
    await render()
    await act(async () => setValue(body().querySelectorAll<HTMLInputElement>('[data-row] input')[0], 'Mine'))
    await act(async () => body().querySelector<HTMLButtonElement>('[aria-label="Back to the rule"]')!.click())

    expect(rows()).toEqual(['ch1', 'ch2'])
  })
})
