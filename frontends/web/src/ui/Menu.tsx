import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import { Check, ChevronLeft, ChevronRight, type LucideIcon } from 'lucide-react'
import { Icon } from './Icon'
import css from './Menu.module.css'

export interface MenuItem {
  label: string
  /** Не нужен пункту с подменю. */
  onSelect?: () => void
  danger?: boolean
  selected?: boolean
  disabled?: boolean
  icon?: LucideIcon
  /** Значок слева, когда нужен не просто icon: например, статус с анимацией. */
  lead?: ReactNode
  /** Пояснение мелким текстом под названием: что именно сделает пункт. */
  hint?: string
  /** Текущее значение справа, например выбранная коллекция. */
  value?: string
  /** Подменю: открывается сбоку при наведении. */
  items?: MenuItem[]
  /** Страница: заменяет содержимое меню, когда пунктам нужно поле ввода. */
  page?: MenuPage
  /** Линия над пунктом: начало новой группы. */
  separated?: boolean
  /** Выбор не закрывает меню: для пунктов-переключателей. */
  keepOpen?: boolean
}

export interface MenuPage {
  items: MenuItem[]
  footer?: (close: () => void) => ReactNode
}

interface MenuProps {
  trigger: ReactNode
  items: MenuItem[]
  /** Нижняя часть меню, например поле ввода. Получает функцию закрытия. */
  footer?: (close: () => void) => ReactNode
  emptyText?: string
  align?: 'start' | 'end'
  openOn?: 'click' | 'contextmenu'
}

export function Menu({ trigger, items, footer, emptyText, align = 'end', openOn = 'click' }: MenuProps) {
  const [open, setOpen] = useState(false)
  const [pageLabel, setPageLabel] = useState<string | null>(null)
  const rootRef = useRef<HTMLSpanElement>(null)

  // Не удлиняем страницу: если снизу не хватает места, а сверху хватает — открываемся вверх.
  const placeMenu = (menu: HTMLDivElement | null) => {
    if (!menu || !rootRef.current) return
    const trigger = rootRef.current.getBoundingClientRect()
    const height = menu.getBoundingClientRect().height
    menu.classList.toggle(css.up, trigger.bottom + height > window.innerHeight && trigger.top > height)
    // Не вылезаем за край окна: на узком экране меню у кнопки посередине строки иначе обрезается.
    const style = getComputedStyle(menu)
    const edge = parseFloat(style.getPropertyValue('--page-x'))
    const applied = parseFloat(style.getPropertyValue('--menu-shift')) || 0
    const box = menu.getBoundingClientRect()
    const left = box.left - applied
    const right = box.right - applied
    const shift = Math.max(0, edge - left) - Math.max(0, right - (window.innerWidth - edge))
    menu.style.setProperty('--menu-shift', `${shift}px`)
  }

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const close = () => setOpen(false)
  const triggerProps = openOn === 'click'
    ? { onClick: (e: MouseEvent) => { e.stopPropagation(); setPageLabel(null); setOpen(o => !o) } }
    : { onContextMenu: (e: MouseEvent) => { e.preventDefault(); setPageLabel(null); setOpen(true) } }
  const pageItem = pageLabel === null ? undefined : findPageItem(items, pageLabel)
  const page = pageItem?.page
  const shownItems = page ? page.items : items
  const shownFooter = page ? page.footer : footer
  const side = align === 'end' ? 'left' : 'right'

  return (
    <span className={css.root} ref={rootRef}>
      <span className={css.trigger} {...triggerProps}>{trigger}</span>
      {open && (
        <div key={pageLabel ?? ''} ref={placeMenu} className={`${css.menu} ${css[align]}`} role="menu" onClick={e => e.stopPropagation()}>
          {pageItem && (
            <button type="button" className={`${css.item} ${css.back}`} onClick={() => setPageLabel(null)}>
              <Icon as={ChevronLeft} size="s" />
              <span className={css.label}>{pageItem.label}</span>
            </button>
          )}
          {shownItems.length === 0 && !page && emptyText && <div className={css.empty}>{emptyText}</div>}
          {shownItems.map((item, index) => (
            <MenuEntry key={index} item={item} side={side} onDone={close} onOpenPage={setPageLabel} />
          ))}
          {shownFooter && <div className={css.footer}>{shownFooter(close)}</div>}
        </div>
      )}
    </span>
  )
}

function findPageItem(items: MenuItem[], label: string): MenuItem | undefined {
  for (const item of items) {
    if (item.page && item.label === label) return item
    const nested = item.items && findPageItem(item.items, label)
    if (nested) return nested
  }
  return undefined
}

interface MenuEntryProps {
  item: MenuItem
  side: 'left' | 'right'
  onDone: () => void
  onOpenPage: (label: string) => void
}

function MenuEntry({ item, side, onDone, onOpenPage }: MenuEntryProps) {
  const [subOpen, setSubOpen] = useState(false)
  const classes = [css.item, item.danger && css.danger, item.items && subOpen && css.active].filter(Boolean).join(' ')
  const select = () => {
    if (item.items) { setSubOpen(open => !open); return }
    if (item.page) { onOpenPage(item.label); return }
    if (!item.keepOpen) onDone()
    item.onSelect?.()
  }
  return (
    <div
      className={css.entry}
      onPointerEnter={e => e.pointerType === 'mouse' && item.items && setSubOpen(true)}
      onPointerLeave={e => e.pointerType === 'mouse' && setSubOpen(false)}
    >
      {item.separated && <div className={css.separator} />}
      <button
        type="button"
        role="menuitem"
        aria-haspopup={item.items || item.page ? 'menu' : undefined}
        aria-expanded={item.items ? subOpen : undefined}
        disabled={item.disabled}
        className={classes}
        onClick={select}
      >
        {item.lead ? <span className={css.lead}>{item.lead}</span> : item.icon && <Icon as={item.icon} size="s" />}
        <span className={css.label}>
          {item.label}
          {item.hint && <span className={css.hint}>{item.hint}</span>}
        </span>
        {item.value && <span className={css.value}>{item.value}</span>}
        {item.selected && <span className={css.check}><Icon as={Check} size="s" /></span>}
        {item.items && <Icon as={side === 'left' ? ChevronLeft : ChevronRight} size="s" />}
        {item.page && <Icon as={ChevronRight} size="s" />}
      </button>
      {item.items && subOpen && (
        <div className={`${css.menu} ${css.submenu} ${css[side]}`} role="menu">
          {item.items.map((child, index) => <MenuEntry key={index} item={child} side={side} onDone={onDone} onOpenPage={onOpenPage} />)}
        </div>
      )}
    </div>
  )
}
