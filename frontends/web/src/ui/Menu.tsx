import { useEffect, useImperativeHandle, useRef, useState, type MouseEvent, type ReactNode, type Ref } from 'react'
import { Check, ChevronLeft, ChevronRight, type LucideIcon } from 'lucide-react'
import { usePhone } from '@/lib/device'
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
  /** Подменю: открывается сбоку при наведении, на телефоне заменяет содержимое меню. */
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

/** Открыть меню не кликом, а, например, с клавиатуры. */
export interface MenuHandle {
  open: () => void
  close: () => void
  isOpen: () => boolean
}

interface MenuProps {
  ref?: Ref<MenuHandle>
  trigger: ReactNode
  items: MenuItem[]
  /** Нижняя часть меню, например поле ввода. Получает функцию закрытия. */
  footer?: (close: () => void) => ReactNode
  emptyText?: string
  align?: 'start' | 'end'
  openOn?: 'click' | 'contextmenu'
}

export function Menu({ ref, trigger, items, footer, emptyText, align = 'end', openOn = 'click' }: MenuProps) {
  const [open, setOpen] = useState(false)
  // Путь из названий пунктов, в которые меню провалилось: страницы и, на телефоне, подменю.
  const [trail, setTrail] = useState<string[]>([])
  const drill = usePhone()
  const openRef = useRef(open)
  useEffect(() => { openRef.current = open }, [open])
  useImperativeHandle(ref, () => ({
    open: () => { setTrail([]); setOpen(true) },
    close: () => setOpen(false),
    isOpen: () => openRef.current,
  }), [])
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
    ? { onClick: (e: MouseEvent) => { e.stopPropagation(); setTrail([]); setOpen(o => !o) } }
    : { onContextMenu: (e: MouseEvent) => { e.preventDefault(); setTrail([]); setOpen(true) } }
  const level = openedLevels(items, trail).at(-1)
  const shownItems = level ? level.items ?? level.page?.items ?? [] : items
  const shownFooter = level ? level.page?.footer : footer
  const openLevel = (label: string) => setTrail(path => [...path, label])
  const side = align === 'end' ? 'left' : 'right'

  return (
    <span className={css.root} ref={rootRef}>
      <span className={css.trigger} {...triggerProps}>{trigger}</span>
      {open && (
        <div key={trail.join('/')} ref={placeMenu} className={`${css.menu} ${css[align]}`} role="menu" onClick={e => e.stopPropagation()}>
          {level && (
            <button type="button" className={`${css.item} ${css.back}`} onClick={() => setTrail(path => path.slice(0, -1))}>
              <Icon as={ChevronLeft} size="s" />
              <span className={css.label}>{level.label}</span>
            </button>
          )}
          {shownItems.length === 0 && !level && emptyText && <div className={css.empty}>{emptyText}</div>}
          {shownItems.map((item, index) => (
            <MenuEntry key={index} item={item} side={side} drill={drill} onDone={close} onOpenLevel={openLevel} />
          ))}
          {shownFooter && <div className={css.footer}>{shownFooter(close)}</div>}
        </div>
      )}
    </span>
  )
}

function openedLevels(items: MenuItem[], trail: string[]): MenuItem[] {
  const levels: MenuItem[] = []
  let shown = items
  for (const label of trail) {
    const found = findLevel(shown, label)
    if (!found) break
    levels.push(found)
    shown = found.items ?? found.page?.items ?? []
  }
  return levels
}

/** Страница может лежать и в подменю, открытом сбоку: ищем на всю глубину. */
function findLevel(items: MenuItem[], label: string): MenuItem | undefined {
  for (const item of items) {
    if ((item.page || item.items) && item.label === label) return item
    const nested = item.items && findLevel(item.items, label)
    if (nested) return nested
  }
  return undefined
}

interface MenuEntryProps {
  item: MenuItem
  side: 'left' | 'right'
  /** Подменю не раскрывается сбоку, а открывается вместо меню, как страница. */
  drill: boolean
  onDone: () => void
  onOpenLevel: (label: string) => void
}

function MenuEntry({ item, side, drill, onDone, onOpenLevel }: MenuEntryProps) {
  const [subOpen, setSubOpen] = useState(false)
  const classes = [css.item, item.danger && css.danger, item.items && subOpen && css.active].filter(Boolean).join(' ')
  const select = () => {
    if (item.items && !drill) { setSubOpen(open => !open); return }
    if (item.items || item.page) { onOpenLevel(item.label); return }
    if (!item.keepOpen) onDone()
    item.onSelect?.()
  }
  return (
    <div
      className={css.entry}
      onPointerEnter={e => e.pointerType === 'mouse' && item.items && !drill && setSubOpen(true)}
      onPointerLeave={e => e.pointerType === 'mouse' && setSubOpen(false)}
    >
      {item.separated && <div className={css.separator} />}
      <button
        type="button"
        role="menuitem"
        aria-haspopup={item.items || item.page ? 'menu' : undefined}
        aria-expanded={item.items && !drill ? subOpen : undefined}
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
        {item.items && <Icon as={side === 'left' && !drill ? ChevronLeft : ChevronRight} size="s" />}
        {item.page && <Icon as={ChevronRight} size="s" />}
      </button>
      {item.items && subOpen && !drill && (
        <div className={`${css.menu} ${css.submenu} ${css[side]}`} role="menu">
          {item.items.map((child, index) => <MenuEntry key={index} item={child} side={side} drill={drill} onDone={onDone} onOpenLevel={onOpenLevel} />)}
        </div>
      )}
    </div>
  )
}
