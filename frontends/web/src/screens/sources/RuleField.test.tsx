import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NamingVariable } from '@/api/types'
import { RuleField } from './RuleField'

const VARIABLES: NamingVariable[] = [
  { token: '{{collection}}', label: 'Collection' },
  { token: '{{n}}', label: 'Number' },
  { token: '{{title}}', label: 'Title from file' },
]

describe('RuleField', () => {
  let host: HTMLDivElement
  let root: Root
  const onChange = vi.fn()

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    onChange.mockReset()
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  const render = (value: string) => act(() => root.render(<RuleField value={value} variables={VARIABLES} onChange={onChange} />))
  const chips = () => [...host.querySelectorAll('[data-token]')].map(chip => chip.getAttribute('data-token'))
  const texts = () => [...host.querySelectorAll('input')].map(input => input.value)
  const button = (label: string) => [...host.querySelectorAll('button')].find(b => b.textContent === label)!

  it('shows variables as chips and the rest as text', () => {
    render('{{collection}} ch{{n}}')

    expect(chips()).toEqual(['{{collection}}', '{{n}}'])
    expect(texts()).toEqual(['', ' ch', ''])
  })

  it('appends a variable from its button', () => {
    render('{{collection}} ch{{n}}')

    act(() => button('+ Title from file').click())

    expect(onChange).toHaveBeenCalledWith('{{collection}} ch{{n}}{{title}}')
  })

  it('removes a chip', () => {
    render('{{collection}} ch{{n}}')

    act(() => host.querySelector<HTMLButtonElement>('[aria-label="Remove Collection"]')!.click())

    expect(onChange).toHaveBeenCalledWith(' ch{{n}}')
  })

  it('edits the text between chips', () => {
    render('{{collection}} ch{{n}}')
    const input = host.querySelectorAll('input')[1]

    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, ' part ')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })

    expect(onChange).toHaveBeenCalledWith('{{collection}} part {{n}}')
  })
})
