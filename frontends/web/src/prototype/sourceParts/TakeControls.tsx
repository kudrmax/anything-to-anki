// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { ChevronDown, Plus } from 'lucide-react'
import { Button, Icon, Menu, type MenuItem } from '@/ui'
import { WHOLE, type Scope, type Source, type TakeOrder } from './mockData'
import { cardsIn, readyProgress, takeLabel, wordsLeft } from './model'
import type { TakeCount } from './prototypeContext'
import css from './prototype.module.css'

const COUNTS = [50, 100, 200]
const ORDERS: { order: TakeOrder; label: string; hint: string }[] = [
  { order: 'useful', label: 'Most useful', hint: 'Frequent words you don’t know yet' },
  { order: 'text', label: 'Text order', hint: 'A continuous piece after the last taken phrase' },
  { order: 'key', label: 'Key words', hint: 'Words this part is about' },
]

const scopeValue = (source: Source, scope: Scope): string => {
  const { decided, total } = readyProgress(cardsIn(source, scope))
  return `${decided}/${total} · ~${wordsLeft(source, scope)} left`
}

interface PartPickerProps {
  source: Source
  scope: Scope
  label: string
  onChange: (scope: Scope) => void
  onAddPart: () => void
}

export function PartPicker({ source, scope, label, onChange, onAddPart }: PartPickerProps) {
  const items: MenuItem[] = [
    { label: source.wholeLabel, value: scopeValue(source, WHOLE), selected: scope === WHOLE, onSelect: () => onChange(WHOLE) },
    ...source.parts.map((part, index) => ({
      label: part.label === part.title ? part.label : `${part.label} · ${part.title}`,
      value: scopeValue(source, part.id),
      selected: scope === part.id,
      separated: index === 0,
      onSelect: () => onChange(part.id),
    })),
    { label: 'Add part…', icon: Plus, separated: true, onSelect: onAddPart },
  ]
  return (
    <Menu
      align="start"
      items={items}
      trigger={<Button title="Choose the part to take and review words from">{label}<Icon as={ChevronDown} size="s" /></Button>}
    />
  )
}

interface TakeButtonProps {
  /** «from Ch 3»; empty for a source with one part. */
  from: string
  left: number
  count: TakeCount
  order: TakeOrder
  busy: boolean
  onTake: () => void
  onCount: (count: TakeCount) => void
  onOrder: (order: TakeOrder) => void
}

export function TakeButton({ from, left, count, order, busy, onTake, onCount, onOrder }: TakeButtonProps) {
  const items: MenuItem[] = [
    ...COUNTS.map(n => ({ label: String(n), selected: count === n, disabled: n >= left, keepOpen: true, onSelect: () => onCount(n) })),
    { label: `All ${left}`, selected: count === 'all' || count >= left, keepOpen: true, onSelect: () => onCount('all') },
    ...ORDERS.map((o, i) => ({ label: o.label, hint: o.hint, selected: order === o.order, separated: i === 0, keepOpen: true, onSelect: () => onOrder(o.order) })),
  ]
  return (
    <div className={css.split}>
      <Button className={css.splitMain} busy={busy} disabled={left === 0} onClick={onTake}>
        {busy ? 'Rebuilding…' : takeLabel(from, left, count)}
      </Button>
      <Menu
        items={items}
        align="start"
        trigger={<Button className={css.splitArrow} disabled={busy || left === 0} aria-label="How many and in what order"><Icon as={ChevronDown} size="s" /></Button>}
      />
    </div>
  )
}
