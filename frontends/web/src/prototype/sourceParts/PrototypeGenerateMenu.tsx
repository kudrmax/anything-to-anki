// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { Plus, RefreshCw, RotateCcw, Sparkles, X } from 'lucide-react'
import { Button, Icon, Menu, Spinner, StatusDot, type MenuItem } from '@/ui'
import css from '@/screens/review/review.module.css'
import type { GenKind, GenMode } from './prototypeContext'

const KINDS: { kind: GenKind; label: string; hint: string }[] = [
  { kind: 'polish', label: 'Phrases', hint: 'AI simplifies phrases' },
  { kind: 'meaning', label: 'Meanings', hint: 'Definition, translation' },
  { kind: 'tts', label: 'Speech', hint: 'Phrase read aloud' },
]

interface GenerateMenuProps {
  done: number
  total: number
  running: GenKind[]
  onRun: (kind: GenKind, mode: GenMode) => void
  onCancel: (kind: GenKind) => void
}

/** Same two-level look as the real GenerateMenu; every kind follows the phrase's single «generated» flag. */
export function PrototypeGenerateMenu({ done, total, running, onRun, onCancel }: GenerateMenuProps) {
  const lead = (busy: boolean) => {
    if (busy) return <Spinner />
    if (total > 0 && done === total) return <StatusDot tone="ok" />
    return <StatusDot />
  }
  const items: MenuItem[] = KINDS.map(({ kind, label, hint }) => {
    const busy = running.includes(kind)
    return {
      label,
      hint,
      lead: lead(busy),
      value: `${done}/${total}`,
      items: [
        { label: 'Generate missing', hint: 'Cards that don’t have it yet', icon: Plus, value: String(total - done), disabled: busy || total === done, onSelect: () => onRun(kind, 'missing') },
        { label: 'Retry failed', hint: 'Cards whose last try failed', icon: RotateCcw, value: '0', disabled: true },
        { label: 'Regenerate all', hint: 'Replace it on every card', icon: RefreshCw, value: String(total), disabled: busy || total === 0, separated: true, onSelect: () => onRun(kind, 'all') },
        { label: 'Cancel', hint: 'Stop queued and running', icon: X, value: busy ? String(total - done) : '0', danger: true, disabled: !busy, separated: true, onSelect: () => onCancel(kind) },
      ],
    }
  })
  return (
    <Menu
      items={items}
      trigger={
        <Button variant="link" className={css.iconTrigger} title="Generate phrases, meanings, audio for this part" aria-label="Generate">
          {running.length > 0 ? <Spinner /> : <Icon as={Sparkles} />}
        </Button>
      }
    />
  )
}
