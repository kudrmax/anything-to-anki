import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import type { InputDescription } from '@/api/types'
import { AddSourceForm } from './AddSourceForm'

const DROPPED = '/books/novel.epub'
const DESCRIBE_DELAY_MS = 300

const NOTHING: InputDescription = { kind: null, format: null, label: null, problem: null, problem_message: null, problem_hint: null }
const PHRASE: InputDescription = { ...NOTHING, kind: 'phrase' }
const TOPIC: InputDescription = { ...NOTHING, kind: 'topic' }
const BOOK: InputDescription = { ...NOTHING, kind: 'source', format: 'epub', label: 'Book · epub' }
const VIDEO_LINK: InputDescription = { ...NOTHING, kind: 'source', format: 'youtube', label: 'Video · YouTube' }
const TEXT: InputDescription = { ...NOTHING, kind: 'source', format: 'plain', label: 'Text' }
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
})
