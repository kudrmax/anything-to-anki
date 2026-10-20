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
  const texts = () => [...host.querySelectorAll('[data-text]')].map(part => part.textContent)
  const input = () => host.querySelector('input')!
  const typeInto = (value: string) => act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input(), value)
    input().dispatchEvent(new Event('input', { bubbles: true }))
  })
  const button = (label: string) => [...host.querySelectorAll('button')].find(b => b.textContent === label)!

  it('shows variables as chips and own text as a chip with every space visible', () => {
    render('{{collection}}  ch{{n}}')

    expect(chips()).toEqual(['{{collection}}', '{{n}}'])
    expect(texts()).toEqual(['··ch'])
    expect(host.querySelector('input')).toBeNull()
  })

  it('appends a variable from its button', () => {
    render('{{collection}} ch{{n}}')

    act(() => button('+ Title from file').click())

    expect(onChange).toHaveBeenCalledWith('{{collection}} ch{{n}} {{title}}')
  })

  it('removes a chip', () => {
    render('{{collection}} ch{{n}}')

    act(() => host.querySelector<HTMLButtonElement>('[aria-label="Remove Collection"]')!.click())

    expect(onChange).toHaveBeenCalledWith(' ch{{n}}')
  })

  it('edits own text in place', () => {
    render('{{collection}} ch{{n}}')

    act(() => host.querySelector<HTMLElement>('[data-text]')!.click())
    expect(input().value).toBe(' ch')
    expect(document.activeElement).toBe(input())
    typeInto(' part ')

    expect(onChange).toHaveBeenCalledWith('{{collection}} part {{n}}')
  })

  it('types between chips where there is no text yet', () => {
    render('{{collection}}{{n}}')

    act(() => host.querySelectorAll<HTMLElement>('[data-slot]')[1].click())
    typeInto(' ch')

    expect(onChange).toHaveBeenCalledWith('{{collection}} ch{{n}}')
  })

  it('puts the cursor at the end on a click in the field', () => {
    render('{{collection}} ch{{n}}')

    act(() => host.querySelector<HTMLElement>('[data-rule-field]')!.click())
    typeInto('!')

    expect(onChange).toHaveBeenCalledWith('{{collection}} ch{{n}}!')
  })

  it('appends to an empty rule without a space', () => {
    render('')

    act(() => button('+ Number').click())

    expect(onChange).toHaveBeenCalledWith('{{n}}')
  })
})
