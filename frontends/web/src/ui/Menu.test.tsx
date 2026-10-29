import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Menu, type MenuItem } from './Menu'

const phone = vi.hoisted(() => ({ on: false }))
vi.mock('@/lib/device', () => ({ usePhone: () => phone.on }))

const ITEMS: MenuItem[] = [
  { label: 'Export' },
  {
    label: 'Generate',
    items: [
      { label: 'Phrases', items: [{ label: 'Generate missing' }] },
      { label: 'Meanings', items: [{ label: 'Generate next 100' }, { label: 'Regenerate all' }] },
    ],
  },
]

describe('Menu', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
    act(() => root.render(<Menu trigger={<button type="button">More</button>} items={ITEMS} />))
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
    phone.on = false
  })

  const button = (label: string) => [...host.querySelectorAll('button')].find(b => b.textContent === label)
  const click = (label: string) => act(() => { button(label)?.click() })
  const shown = () => [...host.querySelectorAll('[role="menuitem"]')].map(b => b.textContent)

  it('opens a submenu beside its item on a desktop', () => {
    click('More')
    click('Generate')
    expect(shown()).toEqual(['Export', 'Generate', 'Phrases', 'Meanings'])
  })

  it('opens a submenu in place of the menu on a phone, with a way back', () => {
    phone.on = true
    click('More')
    click('Generate')
    expect(shown()).toEqual(['Phrases', 'Meanings'])
    click('Meanings')
    expect(shown()).toEqual(['Generate next 100', 'Regenerate all'])
    click('Meanings')
    expect(shown()).toEqual(['Phrases', 'Meanings'])
    click('Generate')
    expect(shown()).toEqual(['Export', 'Generate'])
  })
})
