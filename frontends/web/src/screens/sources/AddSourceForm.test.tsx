import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { CollectionTree, InputDescription, NamingRequired, Question } from '@/api/types'
import { AddSourceForm } from './AddSourceForm'

const DROPPED = '/books/novel.epub'
const BATCH_TEXT = '/a/1.txt\n/a/2.txt'
const DESCRIBE_DELAY_MS = 300

const NOTHING: InputDescription = { kind: null, format: null, label: null, problem: null, problem_message: null, problem_hint: null }
const PHRASE: InputDescription = { ...NOTHING, kind: 'phrase' }
const TOPIC: InputDescription = { ...NOTHING, kind: 'topic' }
const BOOK: InputDescription = { ...NOTHING, kind: 'source', format: 'epub', label: 'Book · epub' }
const VIDEO_LINK: InputDescription = { ...NOTHING, kind: 'source', format: 'youtube', label: 'Video · YouTube' }
const TEXT: InputDescription = { ...NOTHING, kind: 'source', format: 'plain', label: 'Text' }
const BATCH: InputDescription = { ...NOTHING, kind: 'source', label: '2 files', several: true }
const EMPTY_TREE = { collections: [] } as unknown as CollectionTree
const ASK_KIND = (indexes: number[], label: string | null): Question => ({
  id: 'text.kind', prompt: 'Add as', default: 'text', input_indexes: indexes, input_label: label,
  options: [{ id: 'text', label: 'Text', details: null, facts: [] }, { id: 'song', label: 'Song', details: null, facts: [] }],
})
const NAMING: NamingRequired = {
  heading: 'Add 2 files',
  items: [{ label: '1.txt', own_title: '1', words: 3 }, { label: '2.txt', own_title: '2', words: 3 }],
  default_collection: null,
  default_rule: 'Part {{n}}',
  variables: [{ token: '{{n}}', label: 'Number' }],
  number_formats: [{ digits: null, label: 'Auto' }],
}
const BAD_LINK: InputDescription = {
  ...NOTHING, problem: 'unsupported_link', problem_message: "This link can't be read", problem_hint: 'Supported: YouTube.',
}
const NO_FILE: InputDescription = {
  ...NOTHING, problem: 'file_not_found', problem_message: 'No file at this path', problem_hint: 'Check the path.',
}

/** Что backend ответит на каждый ввод; неизвестный ввод — без описания. */
const answers = new Map<string, InputDescription>([
  ['She shrugged off the comment.', PHRASE],
  ['She shrugged off the comment. Then she left.', TEXT],
  ['medicine', TOPIC],
  ['медицина', TOPIC],
  [DROPPED, BOOK],
  ['https://www.youtube.com/watch?v=abc', VIDEO_LINK],
  ['https://example.com/article', BAD_LINK],
  ['/no/such/file.epub', NO_FILE],
  [BATCH_TEXT, BATCH],
])

describe('AddSourceForm', () => {
  let host: HTMLDivElement
  let root: Root
  let describeInput: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    vi.useFakeTimers()
    describeInput = vi.spyOn(api, 'describeInput').mockImplementation(text => Promise.resolve(answers.get(text) ?? NOTHING))
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  const render = async () => {
    await act(async () => root.render(
      <MemoryRouter>
        <AddSourceForm onReload={() => Promise.resolve()} onToast={() => {}} />
      </MemoryRouter>,
    ))
  }

  const field = () => host.querySelector('textarea')!
  const setValue = (value: string) => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field(), value)
    field().dispatchEvent(new Event('input', { bubbles: true }))
  }
  /** Набор с клавиатуры: поле меняется без вставки. */
  const type = async (value: string) => {
    await act(async () => setValue(value))
  }
  /** Вставка из буфера: ввод заменён целиком. */
  const paste = async (value: string) => {
    await act(async () => {
      field().dispatchEvent(new Event('paste', { bubbles: true }))
      setValue(value)
    })
  }
  const described = async () => {
    await act(async () => { await vi.advanceTimersByTimeAsync(DESCRIBE_DELAY_MS) })
  }
  const buttons = () => [...host.querySelectorAll('button')]
  const button = (label: string) => buttons().find(b => b.textContent?.trim() === label)
  const addButton = () => buttons().find(b => b.textContent?.startsWith('Add '))
  const pressedMode = () => buttons().find(b => b.getAttribute('aria-pressed') === 'true')?.textContent
  const choose = async (mode: string) => {
    await act(async () => button(mode)!.click())
  }
  const text = () => host.textContent ?? ''

  it('shows nothing to add while the field is empty', async () => {
    await render()

    expect(addButton()).toBeUndefined()
    expect(describeInput).not.toHaveBeenCalled()
  })

  it('suggests a phrase for one sentence', async () => {
    await render()
    await type('She shrugged off the comment.')
    await described()

    expect(pressedMode()).toBe('Phrase')
    expect(addButton()?.textContent).toBe('Add phrase')
  })

  it.each([['medicine'], ['медицина']])('suggests a topic for %s', async input => {
    await render()
    await type(input)
    await described()

    expect(pressedMode()).toBe('Topic')
    expect(addButton()?.textContent).toBe('Add topic')
  })

  it.each([
    ['https://www.youtube.com/watch?v=abc', 'Video · YouTube'],
    ['She shrugged off the comment. Then she left.', 'Text'],
  ])('suggests a source for %s and says how it will be read', async (input, label) => {
    await render()
    await type(input)
    await described()

    expect(pressedMode()).toBe('Source')
    expect(addButton()?.textContent).toBe('Add source')
    expect(text()).toContain(label)
  })

  it('keeps the chosen mode while typing, even when the suggestion changes', async () => {
    await render()
    await type('She shrugged off the comment.')
    await described()
    await choose('Topic')
    await type('She shrugged off the comment. Then she left.')
    await described()

    expect(pressedMode()).toBe('Topic')
    expect(addButton()?.textContent).toBe('Add topic')
  })

  it('forgets the chosen mode when another input is pasted', async () => {
    await render()
    await type('She shrugged off the comment.')
    await described()
    await choose('Topic')
    await paste('https://www.youtube.com/watch?v=abc')
    await described()

    expect(pressedMode()).toBe('Source')
    expect(addButton()?.textContent).toBe('Add source')
  })

  it('describes the input in any mode, not only in Source', async () => {
    await render()
    await type('She shrugged off the comment.')
    await described()
    await choose('Topic')
    describeInput.mockClear()
    await type('medicine')
    await described()

    expect(describeInput).toHaveBeenCalledWith('medicine', expect.anything())
  })

  it('keeps the last description while the next one is on its way', async () => {
    await render()
    await type('She shrugged off the comment.')
    await described()
    await type('She shrugged off the comment. Then she left.')

    expect(pressedMode()).toBe('Phrase')
    expect(addButton()?.textContent).toBe('Add phrase')
  })

  it.each([
    ['https://example.com/article', "This link can't be read", 'Supported: YouTube.'],
    ['/no/such/file.epub', 'No file at this path', 'Check the path.'],
  ])('blocks adding %s and says why', async (input, message, hint) => {
    await render()
    await type(input)
    await described()

    expect(text()).toContain(message)
    expect(text()).toContain(hint)
    expect(addButton()?.disabled).toBe(true)
    expect(pressedMode()).toBeUndefined()
    expect(host.querySelector('input[placeholder="Title (optional)"]')).toBeNull()
  })

  it('lets adding again once the problem is fixed', async () => {
    await render()
    await type('/no/such/file.epub')
    await described()
    await type(DROPPED)
    await described()

    expect(addButton()?.disabled).toBe(false)
    expect(text()).not.toContain('No file at this path')
  })

  it('drops the chosen mode when the field is cleared', async () => {
    await render()
    await type('She shrugged off the comment.')
    await described()
    await choose('Topic')
    await type('')
    await type('She shrugged off the comment.')
    await described()

    expect(pressedMode()).toBe('Phrase')
  })

  it('hides the title for several files', async () => {
    await render()
    await paste(BATCH_TEXT)
    await described()

    expect(text()).toContain('2 files')
    expect(host.querySelector('input[placeholder="Title (optional)"]')).toBeNull()
  })

  it('asks a question shared by the files once and sends its answer to each', async () => {
    const addSource = vi.spyOn(api, 'addSource')
      .mockResolvedValueOnce({ questions: [ASK_KIND([0, 1], null)] })
      .mockResolvedValueOnce({ source_ids: [1, 2], collection_id: null })
    await render()
    await paste(BATCH_TEXT)
    await described()
    await act(async () => addButton()!.click())
    await act(async () => [...document.body.querySelectorAll('button')].find(b => b.textContent === 'Confirm')!.click())

    expect(addSource).toHaveBeenLastCalledWith(BATCH_TEXT, '', '', [{ 'text.kind': 'text' }, { 'text.kind': 'text' }], undefined)
  })

  it('asks each file its questions, naming the file, and sends answers per file', async () => {
    const addSource = vi.spyOn(api, 'addSource')
      .mockResolvedValueOnce({ questions: [ASK_KIND([0], '1.txt'), ASK_KIND([1], '2.txt')] })
      .mockResolvedValueOnce({ source_ids: [1, 2], collection_id: null })
    await render()
    await paste(BATCH_TEXT)
    await described()
    await act(async () => addButton()!.click())

    expect(document.body.textContent).toContain('1.txt')
    expect(document.body.textContent).toContain('2.txt')
    await act(async () => [...document.body.querySelectorAll('button')].find(b => b.textContent === 'Confirm')!.click())

    expect(addSource).toHaveBeenLastCalledWith(BATCH_TEXT, '', '', [{ 'text.kind': 'text' }, { 'text.kind': 'text' }], undefined)
  })

  it('opens the naming window and sends the naming with the answers', async () => {
    vi.spyOn(api, 'getCollectionTree').mockResolvedValue(EMPTY_TREE)
    vi.spyOn(api, 'renderNames').mockResolvedValue(['Part 1', 'Part 2'])
    const addSource = vi.spyOn(api, 'addSource')
      .mockResolvedValueOnce(NAMING)
      .mockResolvedValueOnce({ source_ids: [1, 2], collection_id: null })
    await render()
    await paste(BATCH_TEXT)
    await described()
    await act(async () => addButton()!.click())

    expect(document.body.textContent).toContain('Add 2 files')
    await described()
    await act(async () => [...document.body.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')].find(b => b.textContent === 'Add')!.click())

    expect(addSource).toHaveBeenLastCalledWith(BATCH_TEXT, '', '', [], { collection: null, rule: 'Part {{n}}', titles: {}, number_digits: null })
  })

  it('names the file without subtitles when several are added', async () => {
    vi.spyOn(api, 'addSource').mockRejectedValue(
      new Error('422: {"detail":{"error":"subtitles_not_available","message":"b.mkv: No subtitles"}}'),
    )
    await render()
    await paste(BATCH_TEXT)
    await described()
    await act(async () => addButton()!.click())

    expect(text()).toContain('b.mkv: No subtitles')
  })
})
