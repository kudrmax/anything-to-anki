import { useState } from 'react'
import { computeDiff } from '@/lib/text/diff'
import { pickedWords, toggled } from '@/lib/text/words'
import { Button, Text, Tooltip, WordPicker } from '@/ui'
import type { SelectionPoint } from './SourceText'
import type { Editing } from './useReview'
import css from './review.module.css'

const WAS_PREVIEW_LENGTH = 50

interface SelectionPopoverProps {
  phrase: string
  point: SelectionPoint
  /** Задан — попап правит границы фрагмента, иначе добавляет новое слово. */
  editing: Editing | null
  onSetBoundary: (phrase: string) => Promise<void>
  onAddWord: (target: string, context: string) => Promise<void>
  onCancel: () => void
}

export function SelectionPopover({ phrase, point, editing, onSetBoundary, onAddWord, onCancel }: SelectionPopoverProps) {
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const target = pickedWords(phrase, selected)

  const run = async (action: () => Promise<void>) => {
    if (loading) return
    setLoading(true)
    try {
      await action()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Tooltip anchor={null} point={point} role="dialog" onClose={onCancel}>
      <div className={css.popover}>
        {editing ? (
          <>
            <Text size="s"><Text tone="accent">{editing.lemma}</Text> <Text tone="muted">{editing.pos} · Edit boundary</Text></Text>
            <div>
              {computeDiff(editing.originalFragment, phrase).map((segment, i) => (
                <span key={i} className={segment.type === 'added' ? css.added : segment.type === 'removed' ? css.removed : undefined}>{segment.text} </span>
              ))}
            </div>
            <Text tone="muted" size="s">
              Was: «{editing.originalFragment.length > WAS_PREVIEW_LENGTH ? editing.originalFragment.slice(0, WAS_PREVIEW_LENGTH) + '…' : editing.originalFragment}»
            </Text>
          </>
        ) : (
          <>
            <Text tone="muted" size="s">Tap words to select target</Text>
            <WordPicker phrase={phrase} selected={selected} onToggle={i => setSelected(prev => toggled(prev, i))} />
            {target && <Text tone="muted" size="s">Target: <Text tone="accent">{target}</Text></Text>}
          </>
        )}
        <div className={css.popoverFooter}>
          <Button variant="link" onClick={onCancel}>Cancel</Button>
          {editing
            ? <Button variant="fill" busy={loading} onClick={() => void run(() => onSetBoundary(phrase))}>Set boundary</Button>
            : <Button variant="fill" busy={loading} disabled={!target} onClick={() => void run(() => onAddWord(target, phrase))}>Add word</Button>}
        </div>
      </div>
    </Tooltip>
  )
}
