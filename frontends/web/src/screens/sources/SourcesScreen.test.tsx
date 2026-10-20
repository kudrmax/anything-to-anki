import { act, useEffect } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { CollectionTree, InputDescription, Scope, ScopeCounts, Settings, SourceBoard, SourceSummary, Stats } from '@/api/types'
import { SourcesScreen } from './SourcesScreen'

const counts: ScopeCounts = {
  total: 3, reviewed: 1, pending: 0, progress: { decided: 0, total: 0 }, status: 'new', can_process: false, can_review: false, review_fraction: 0, progress_caption: '',
  available_operations: ['rebuild'], can_start_operation: true, operation_hint: null, can_export: true,
}
const tree: CollectionTree = {
  all: counts,
  unsorted: counts,
  max_depth: 5,
  collections: [{
    id: 10, name: 'Friends', parent_id: null, counts, depth: 1, accepts_collections: true, move_targets: [null],
    children: [{ id: 11, name: 'Season 1', parent_id: 10, counts, depth: 2, accepts_collections: true, move_targets: [null, 10], children: [] }],
  }],
}

const source = (id: number, title: string, status: SourceSummary['status']): SourceSummary => ({
  id, title, status, kind: 'text', role: 'content', has_video: false, source_url: null, video_downloaded: false,
  created_at: '2026-10-01T00:00:00Z', candidate_count: 4, learn_count: 0, progress: { decided: 1, total: 4 }, processing_stage: null,
  collection_id: null, collection_path: [], stage: 'ready', awaiting_generation: false, generation_status: null,
  generation_error: null, available_operations: [], can_start_operation: true, busy_with: null, operation_hint: null, progress_caption: '4 phrases',
  can_process: status === 'new' || status === 'error', can_review: true, can_export: status !== 'done', can_delete: true, review_fraction: 0.25,
})

const board: SourceBoard = {
  title: 'All sources',
  groups: [
    { stage: 'in_progress', sources: [source(1, 'Pilot', 'partially_reviewed'), source(2, 'Second', 'partially_reviewed')] },
    { stage: 'preparing', sources: [] },
    { stage: 'reviewed', sources: [source(3, 'Finale', 'reviewed')] },
  ],
}

const seen: { location: string; state: unknown } = { location: '', state: null }
function LocationProbe() {
  const current = useLocation()
  useEffect(() => {
    seen.location = current.pathname + current.search
    seen.state = current.state
  }, [current])
  return null
}

describe('SourcesScreen', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.spyOn(api, 'getStats').mockResolvedValue({ learn_count: 0, known_word_count: 0, candidate_count: 0 } as Stats)
    vi.spyOn(api, 'getCollectionTree').mockResolvedValue(tree)
    vi.spyOn(api, 'getSettings').mockResolvedValue({ source_grouping: 'stage', source_sort: 'added', source_sort_direction: 'forward' } as Settings)
    vi.spyOn(api, 'getSourceBoard').mockImplementation((scope: Scope) =>
      scope === 999 ? Promise.reject(new Error('404: {"detail":"Collection not found"}')) : Promise.resolve(board))
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
    vi.restoreAllMocks()
  })

  const settle = () => act(async () => {
    for (let i = 0; i < 5; i++) await new Promise(resolve => setTimeout(resolve, 0))
  })

  const render = async (url = '/') => {
    act(() => root.render(
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/" element={<><SourcesScreen /><LocationProbe /></>} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    ))
    await settle()
  }

  const rows = () => [...host.querySelectorAll<HTMLElement>('[role="option"]')]
  const row = (title: string) => rows().find(el => el.textContent?.includes(title))!
  const button = (label: string, scope: ParentNode = document.body) =>
    [...scope.querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent?.trim() === label || el.getAttribute('aria-label') === label)!
  const toasts = () => [...document.body.querySelectorAll('[role="status"]')].map(el => el.textContent).join(' | ')
  const press = (key: string, init: KeyboardEventInit = {}) =>
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...init })) })

  const addForm = () => host.querySelector<HTMLElement>('[aria-label="Add"]')
  const typeInto = async (field: HTMLTextAreaElement, value: string) => {
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field, value)
      field.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }

  it('offers adding at the top of the side column', async () => {
    await render()
    const side = host.querySelector('aside')!
    expect(side.firstElementChild).toBe(addForm())
    expect(addForm()!.querySelector('textarea')).not.toBeNull()
  })

  it('on a phone offers adding above the list', async () => {
    document.documentElement.style.setProperty('--desktop-display', 'none')
    try {
      await render()
      expect(host.querySelector('aside')).toBeNull()
      expect(addForm()!.querySelector('textarea')).not.toBeNull()
    } finally {
      document.documentElement.style.removeProperty('--desktop-display')
    }
  })

  it('shows the added source in the list without leaving the screen', async () => {
    const text: InputDescription = { kind: 'source', format: 'plain', label: 'Text', problem: null, problem_message: null, problem_hint: null }
    vi.spyOn(api, 'describeInput').mockResolvedValue(text)
    const addSource = vi.spyOn(api, 'addSource').mockResolvedValue({ source_ids: [4], collection_id: null })
    await render()
    const loads = vi.mocked(api.getSourceBoard).mock.calls.length

    await typeInto(addForm()!.querySelector('textarea')!, 'Some text to learn from.')
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 350)) })
    await settle()
    act(() => button('Add source', addForm()!).click())
    await settle()

    expect(addSource).toHaveBeenCalledWith('Some text to learn from.', '', '', [], undefined)
    expect(vi.mocked(api.getSourceBoard).mock.calls.length).toBeGreaterThan(loads)
    expect(seen.location).toBe('/')
    expect(addForm()!.querySelector('textarea')!.value).toBe('')
  })

  it('renders the stage groups of the board', async () => {
    await render()
    const headings = [...host.querySelectorAll('h2')].map(h => h.textContent)
    expect(headings).toEqual(['In progress2', 'Reviewed1'])
    expect(rows().map(r => r.querySelector('[class*="title"]')?.textContent)).toEqual(['Pilot', 'Second', 'Finale'])
    expect(host.querySelector('[role="listbox"]')?.getAttribute('aria-multiselectable')).toBe('true')
    expect(button('Continue', row('Pilot')).className).toMatch(/fill/)
    expect(button('Continue', row('Second')).className).not.toMatch(/fill/)
  })

  const openView = (name: 'Group' | 'Sort') => {
    act(() => button('Actions').click())
    const entry = [...document.body.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')]
      .find(el => el.textContent?.startsWith(name))!
    act(() => entry.click())
    return entry
  }

  it('keeps the grouping and the sort in the actions menu, showing what the settings hold', async () => {
    await render()
    expect(button('Group: By status')).toBeUndefined()
    act(() => button('Actions').click())
    const entries = [...document.body.querySelectorAll('[role="menuitem"]')].map(el => el.textContent)
    expect(entries).toContain('GroupBy status')
    expect(entries).toContain('SortDate added')
  })

  it('saves a new sort in the settings and reloads the board', async () => {
    const update = vi.spyOn(api, 'updateSettings').mockResolvedValue({ source_grouping: 'stage', source_sort: 'name', source_sort_direction: 'forward' } as Settings)
    await render()
    const loads = vi.mocked(api.getSourceBoard).mock.calls.length

    openView('Sort')
    act(() => button('Name').click())
    await settle()

    expect(update).toHaveBeenCalledWith({ source_sort: 'name' })
    expect(vi.mocked(api.getSourceBoard).mock.calls.length).toBe(loads + 1)
    expect(openView('Sort').textContent).toBe('SortName')
  })

  it('reverses the sort, naming the direction after the sort', async () => {
    const update = vi.spyOn(api, 'updateSettings').mockResolvedValue({ source_grouping: 'stage', source_sort: 'added', source_sort_direction: 'reverse' } as Settings)
    await render()

    openView('Sort')
    act(() => button('Oldest first').click())
    await settle()

    expect(update).toHaveBeenCalledWith({ source_sort_direction: 'reverse' })
    openView('Sort')
    expect(button('Oldest first').querySelector('svg')).not.toBeNull()
    expect(button('Newest first').querySelector('svg')).toBeNull()
  })

  it('saves a new grouping in the settings', async () => {
    const update = vi.spyOn(api, 'updateSettings').mockResolvedValue({ source_grouping: 'none', source_sort: 'added', source_sort_direction: 'forward' } as Settings)
    await render()

    openView('Group')
    act(() => button('None').click())
    await settle()

    expect(update).toHaveBeenCalledWith({ source_grouping: 'none' })
    expect(openView('Group').textContent).toBe('GroupNone')
  })

  it('renders an ungrouped board as one list without a heading', async () => {
    vi.mocked(api.getSourceBoard).mockResolvedValue({
      title: 'All sources',
      groups: [{ stage: null, sources: [source(3, 'Finale', 'reviewed'), source(1, 'Pilot', 'partially_reviewed')] }],
    })
    await render()
    expect(host.querySelectorAll('h2')).toHaveLength(0)
    expect(rows().map(r => r.textContent?.includes('Finale'))).toEqual([true, false])
    expect(rows()).toHaveLength(2)
  })

  it('keeps one header layout for every scope: nothing moves when switching', async () => {
    const shape = () => {
      const header = host.querySelector('header')!
      const lead = header.firstElementChild!
      const actions = header.lastElementChild!
      return {
        leadLines: lead.children.length,
        actionSlots: actions.children.length,
        search: !!host.querySelector('input[type="search"]'),
      }
    }
    await render('/')
    const all = shape()
    act(() => root.unmount())
    root = createRoot(host)
    await render('/?scope=11')
    expect(shape()).toEqual(all)
    expect(host.querySelector('h1')?.textContent).toBe('FriendsSeason 1')
    expect(all).toEqual({ leadLines: 2, actionSlots: 1, search: true })
  })

  it('opens the parent from the path in the header', async () => {
    await render('/?scope=11')
    act(() => button('Friends', host.querySelector('h1')!).click())
    await settle()
    expect(seen.location).toBe('/?scope=10')
  })

  it('falls back to All when the scope in the URL does not exist', async () => {
    await render('/?scope=999')
    await settle()
    expect(seen.location).toBe('/')
    expect(api.getSourceBoard).toHaveBeenLastCalledWith('all', '', expect.anything())
    expect(toasts()).toBe('')
  })

  it('moves the selected sources and offers Undo', async () => {
    const placeSources = vi.spyOn(api, 'placeSources').mockResolvedValue({ previous: [{ source_id: 2, collection_id: null }] })
    await render()

    act(() => row('Second').dispatchEvent(new MouseEvent('click', { bubbles: true, metaKey: true })))
    expect(row('Second').getAttribute('aria-selected')).toBe('true')
    expect(seen.location).toBe('/')

    act(() => button('Move to…', host.querySelector('[role="toolbar"]')!).click())
    const dialog = document.body.querySelector('[role="dialog"]')!
    act(() => [...dialog.querySelectorAll<HTMLButtonElement>('[role="option"]')].find(o => o.textContent?.includes('Season 1'))!.click())
    await settle()

    expect(placeSources).toHaveBeenCalledWith([{ source_id: 2, collection_id: 11 }])
    expect(toasts()).toContain('Moved 1 source to Season 1')
    expect(button('Undo')).toBeTruthy()
    expect(host.querySelector('[role="toolbar"]')).toBeNull()
  })

  it('deletes a collection without confirming and offers Undo', async () => {
    const confirm = vi.spyOn(window, 'confirm')
    const deleteCollection = vi.spyOn(api, 'deleteCollection').mockResolvedValue({ id: 11, name: 'Season 1', evicted_source_count: 0 })
    await render('/?scope=11')

    act(() => button('Collection actions', host).click())
    act(() => [...document.body.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')].find(i => i.textContent?.includes('Delete'))!.click())
    await settle()

    expect(confirm).not.toHaveBeenCalled()
    expect(deleteCollection).toHaveBeenCalledWith(11)
    expect(toasts()).toContain('Deleted Season 1')
    expect(seen.location).toBe('/')
  })

  it('selects everything with Cmd-A and clears with Esc', async () => {
    await render()
    press('a', { metaKey: true })
    expect(rows().every(r => r.getAttribute('aria-selected') === 'true')).toBe(true)
    expect(host.textContent).toContain('3 selected')
    press('Escape')
    expect(rows().some(r => r.getAttribute('aria-selected') === 'true')).toBe(false)
  })

  it('keeps the selection of rows that survive a reload', async () => {
    vi.spyOn(api, 'renameSource').mockResolvedValue(undefined as never)
    await render()
    press('a', { metaKey: true })
    vi.mocked(api.getSourceBoard).mockResolvedValue({ ...board, groups: [board.groups[0]] })

    act(() => row('Pilot').querySelector('[class*="title"]')!.dispatchEvent(new MouseEvent('dblclick', { bubbles: true })))
    const input = host.querySelector<HTMLInputElement>('[role="option"] input')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'Pilot 2')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    act(() => { input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
    await settle()

    expect(rows()).toHaveLength(2)
    expect(host.textContent).toContain('2 selected')
  })

  it('opens Review remembering the scope to come back to', async () => {
    await render('/?scope=11')
    act(() => row('Finale').click())
    expect(seen.location).toBe('/review?scope=source-3')
    expect(seen.state).toEqual({ back: '/?scope=11' })
  })

  it('exports the open collection and comes back to it', async () => {
    await render('/?scope=11')
    act(() => button('Collection actions', host.querySelector('header')!).click())
    act(() => button('Export', host.querySelector('header')!).click())
    expect(seen.location).toBe('/export?scope=11')
    expect(seen.state).toEqual({ back: '/?scope=11' })
  })

  it('rebuilds the open collection through the same dialog a source uses', async () => {
    const preview = vi.spyOn(api, 'previewRebuild').mockReturnValue(new Promise(() => {}))
    await render('/?scope=11')
    act(() => button('Collection actions', host.querySelector('header')!).click())
    act(() => button('Rebuild…', host.querySelector('header')!).click())
    const dialog = document.body.querySelector('[role="dialog"]')!
    expect(dialog.textContent).toContain('Rebuild “Season 1”')
    act(() => button('Preview', dialog).click())
    expect(preview).toHaveBeenCalledWith(11)
  })

  it('opens the review of the open collection from its header', async () => {
    const reviewable = { ...counts, status: 'partially_reviewed' as const, can_review: true }
    vi.mocked(api.getCollectionTree).mockResolvedValue({
      ...tree, collections: [{ ...tree.collections[0], counts: reviewable }],
    })
    await render('/?scope=10')
    act(() => button('Continue', host.querySelector('header')!).click())
    expect(seen.location).toBe('/review?scope=10')
    expect(seen.state).toEqual({ back: '/?scope=10' })
  })

  it('drops the selection when the scope changes', async () => {
    await render()
    press('a', { metaKey: true })
    const unsorted = [...host.querySelectorAll<HTMLElement>('[role="treeitem"]')].find(el => el.textContent?.includes('Unsorted'))!
    act(() => unsorted.click())
    await settle()
    expect(seen.location).toBe('/?scope=unsorted')
    expect(host.querySelector('[role="toolbar"]')).toBeNull()
  })

  it('moving one unselected row keeps the selection of other rows', async () => {
    vi.spyOn(api, 'placeSources').mockResolvedValue({ previous: [{ source_id: 3, collection_id: null }] })
    await render()
    act(() => row('Pilot').dispatchEvent(new MouseEvent('click', { bubbles: true, metaKey: true })))
    act(() => row('Second').dispatchEvent(new MouseEvent('click', { bubbles: true, metaKey: true })))

    act(() => button('More', row('Finale')).click())
    act(() => [...document.body.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')].find(i => i.textContent?.includes('Move to'))!.click())
    const dialog = document.body.querySelector('[role="dialog"]')!
    act(() => [...dialog.querySelectorAll<HTMLButtonElement>('[role="option"]')].find(o => o.textContent?.includes('Season 1'))!.click())
    await settle()

    expect(api.placeSources).toHaveBeenCalledWith([{ source_id: 3, collection_id: 11 }])
    expect(host.textContent).toContain('2 selected')
  })

  it('keeps the selection when a move fails', async () => {
    vi.spyOn(api, 'placeSources').mockRejectedValue(new Error('500: boom'))
    await render()
    act(() => row('Second').dispatchEvent(new MouseEvent('click', { bubbles: true, metaKey: true })))

    act(() => button('Move to…', host.querySelector('[role="toolbar"]')!).click())
    const dialog = document.body.querySelector('[role="dialog"]')!
    act(() => [...dialog.querySelectorAll<HTMLButtonElement>('[role="option"]')].find(o => o.textContent?.includes('Season 1'))!.click())
    await settle()

    expect(host.textContent).toContain('1 selected')
  })

  it('shows no empty state until the tree has loaded', async () => {
    let resolveTree: (t: CollectionTree) => void = () => {}
    vi.mocked(api.getCollectionTree).mockReturnValue(new Promise(resolve => { resolveTree = resolve }))
    vi.mocked(api.getSourceBoard).mockResolvedValue({ title: 'Season 1', groups: [] })
    await render('/?scope=11')
    expect(host.textContent).not.toContain('No sources here')
    await act(async () => resolveTree(tree))
    await settle()
    expect(host.textContent).toContain('Drag sources onto it in the tree')
  })

  it('on a phone an empty collection points to Move to only', async () => {
    document.documentElement.style.setProperty('--desktop-display', 'none')
    try {
      vi.mocked(api.getSourceBoard).mockResolvedValue({ title: 'Season 1', groups: [] })
      await render('/?scope=11')
      expect(host.textContent).toContain('choose Move to…')
      expect(host.textContent).not.toContain('Drag sources')
    } finally {
      document.documentElement.style.removeProperty('--desktop-display')
    }
  })
})
