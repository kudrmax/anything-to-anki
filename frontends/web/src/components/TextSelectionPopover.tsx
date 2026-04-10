import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

interface TextSelectionPopoverProps {
  mode: 'edit' | 'add'
  selectedText: string
  position: { x: number; y: number; yBottom: number }
  onCancel: () => void
  // Edit mode
  lemma?: string
  pos?: string
  originalFragment?: string
  onSetBoundary?: (phrase: string) => Promise<void>
  // Add mode
  onAddWord?: (target: string, context: string) => Promise<void>
}

interface DiffSegment {
  text: string
  type: 'same' | 'added' | 'removed'
}

/* ------------------------------------------------------------------ */
/*  Diff algorithm                                                    */
/* ------------------------------------------------------------------ */

function computeDiff(original: string, updated: string, lemma: string): DiffSegment[] {
  const lowerLemma = lemma.toLowerCase()

  const splitAroundLemma = (s: string): { prefix: string; target: string; suffix: string } | null => {
    const lower = s.toLowerCase()
    const idx = lower.indexOf(lowerLemma)
    if (idx === -1) return null
    return {
      prefix: s.slice(0, idx).trimEnd(),
      target: s.slice(idx, idx + lemma.length),
      suffix: s.slice(idx + lemma.length).trimStart(),
    }
  }

  const origParts = splitAroundLemma(original)
  const newParts = splitAroundLemma(updated)

  if (!origParts || !newParts) {
    // Fallback: show whole original as removed, whole updated as added
    const segments: DiffSegment[] = []
    if (original) segments.push({ text: original, type: 'removed' })
    if (updated) segments.push({ text: updated, type: 'added' })
    return segments
  }

  const segments: DiffSegment[] = []

  // Prefix diff
  if (origParts.prefix === newParts.prefix) {
    if (origParts.prefix) segments.push({ text: origParts.prefix, type: 'same' })
  } else {
    if (origParts.prefix) segments.push({ text: origParts.prefix, type: 'removed' })
    if (newParts.prefix) segments.push({ text: newParts.prefix, type: 'added' })
  }

  // Target word is always the same
  segments.push({ text: newParts.target, type: 'same' })

  // Suffix diff
  if (origParts.suffix === newParts.suffix) {
    if (origParts.suffix) segments.push({ text: origParts.suffix, type: 'same' })
  } else {
    if (origParts.suffix) segments.push({ text: origParts.suffix, type: 'removed' })
    if (newParts.suffix) segments.push({ text: newParts.suffix, type: 'added' })
  }

  return segments
}

/* ------------------------------------------------------------------ */
/*  Shared popover shell                                              */
/* ------------------------------------------------------------------ */

function PopoverShell({
  position,
  onCancel,
  children,
}: {
  position: { x: number; y: number; yBottom: number }
  onCancel: () => void
  children: React.ReactNode
}) {
  const [flipped, setFlipped] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    if (rect.top < 8) setFlipped(true)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onCancel()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [onCancel])

  return (
    <div
      ref={ref}
      className="popover-fade-in"
      style={{
        position: 'fixed',
        left: position.x,
        top: flipped ? position.yBottom : position.y,
        transform: `translateX(-50%) translateY(${flipped ? '8px' : 'calc(-100% - 8px)'})`,
        zIndex: 50,
        background: 'var(--glass)',
        border: '1px solid var(--glass-b)',
        boxShadow: 'var(--sh)',
        backdropFilter: 'var(--blur)',
        WebkitBackdropFilter: 'var(--blur)',
        borderRadius: '0.75rem',
        padding: '0.625rem 0.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        maxWidth: '360px',
      }}
    >
      {children}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Edit boundary content                                             */
/* ------------------------------------------------------------------ */

function EditBoundaryContent({
  lemma,
  pos,
  originalFragment,
  selectedText,
  onSetBoundary,
  onCancel,
}: {
  lemma: string
  pos: string
  originalFragment: string
  selectedText: string
  onSetBoundary: (phrase: string) => Promise<void>
  onCancel: () => void
}) {
  const [loading, setLoading] = useState(false)

  const diff = computeDiff(originalFragment, selectedText, lemma)

  const handleSet = async () => {
    if (loading) return
    setLoading(true)
    try {
      await onSetBoundary(selectedText)
    } finally {
      setLoading(false)
    }
  }

  const wasPreview = originalFragment.length > 50
    ? originalFragment.slice(0, 50) + '…'
    : originalFragment

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--tm)' }}>
          <span className="font-semibold" style={{ color: 'var(--accent)' }}>{lemma}</span>
          <span style={{ color: 'var(--td)' }}>{pos}</span>
        </div>
        <span
          className="text-[10px] font-medium uppercase tracking-wider"
          style={{ color: 'var(--td)' }}
        >
          Edit boundary
        </span>
      </div>

      {/* Diff preview */}
      <div
        className="text-sm leading-relaxed"
        style={{ color: 'var(--tm)' }}
      >
        {diff.map((seg, i) => {
          if (seg.type === 'removed') {
            return (
              <span
                key={i}
                style={{
                  color: '#ef4444',
                  textDecoration: 'line-through',
                  opacity: 0.8,
                }}
              >
                {seg.text}{' '}
              </span>
            )
          }
          if (seg.type === 'added') {
            return (
              <span
                key={i}
                style={{ color: '#22c55e' }}
              >
                {seg.text}{' '}
              </span>
            )
          }
          return <span key={i}>{seg.text} </span>
        })}
      </div>

      {/* Was subtitle */}
      <p
        className="text-[11px] italic"
        style={{ color: 'var(--td)' }}
      >
        Was: «{wasPreview}»
      </p>

      {/* Buttons */}
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={onCancel}
          className="rounded-lg px-3 py-1 text-xs font-medium transition-all hover:brightness-110 cursor-pointer"
          style={{ color: 'var(--td)' }}
        >
          Cancel
        </button>
        <button
          onClick={() => void handleSet()}
          disabled={loading}
          className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-1 text-xs font-medium text-white disabled:opacity-40 transition-all hover:brightness-110 cursor-pointer"
          style={{ background: 'var(--accent)' }}
        >
          {loading && <Loader2 size={11} className="animate-spin" />}
          Set boundary
        </button>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  Add word content                                                  */
/* ------------------------------------------------------------------ */

function AddWordContent({
  selectedText,
  onAddWord,
  onCancel,
}: {
  selectedText: string
  onAddWord: (target: string, context: string) => Promise<void>
  onCancel: () => void
}) {
  const words = selectedText.split(/\s+/).filter(Boolean)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)

  const hasSelection = selected.size > 0

  const toggleWord = (i: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const targetText = words.filter((_, i) => selected.has(i)).join(' ')

  const handleAdd = async () => {
    if (!hasSelection || loading) return
    setLoading(true)
    try {
      await onAddWord(targetText, selectedText)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Header */}
      <span
        className="text-[10px] font-medium uppercase tracking-wider"
        style={{ color: 'var(--td)' }}
      >
        Tap words to select target
      </span>

      {/* Words as readable text with clickable spans */}
      <div className="text-sm leading-relaxed select-none">
        {words.map((word, i) => (
          <span
            key={i}
            onClick={() => toggleWord(i)}
            className="cursor-pointer transition-all"
            style={{
              color: 'var(--tm)',
              opacity: hasSelection && !selected.has(i) ? 0.5 : 1,
              background: selected.has(i) ? 'rgba(139,92,246,0.2)' : 'transparent',
              borderBottom: selected.has(i) ? '2px solid var(--accent)' : '2px solid transparent',
              borderRadius: '2px',
              padding: '1px 2px',
            }}
          >
            {word}
          </span>
        )).reduce<React.ReactNode[]>((acc, el, i) => {
          if (i > 0) acc.push(<span key={`sp-${i}`}> </span>)
          acc.push(el)
          return acc
        }, [])}
      </div>

      {/* Target preview */}
      {hasSelection && (
        <p className="text-xs" style={{ color: 'var(--td)' }}>
          Target:{' '}
          <span className="font-semibold" style={{ color: 'var(--accent)' }}>
            {targetText}
          </span>
        </p>
      )}

      {/* Buttons */}
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={onCancel}
          className="rounded-lg px-3 py-1 text-xs font-medium transition-all hover:brightness-110 cursor-pointer"
          style={{ color: 'var(--td)' }}
        >
          Cancel
        </button>
        <button
          onClick={() => void handleAdd()}
          disabled={!hasSelection || loading}
          className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-1 text-xs font-medium text-white disabled:opacity-40 transition-all hover:brightness-110 cursor-pointer"
          style={{ background: 'var(--accent)' }}
        >
          {loading && <Loader2 size={11} className="animate-spin" />}
          Add word
        </button>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  Main component                                                    */
/* ------------------------------------------------------------------ */

export function TextSelectionPopover(props: TextSelectionPopoverProps) {
  const { mode, selectedText, position, onCancel } = props

  return (
    <PopoverShell position={position} onCancel={onCancel}>
      {mode === 'edit' && props.lemma && props.originalFragment && props.onSetBoundary && (
        <EditBoundaryContent
          lemma={props.lemma}
          pos={props.pos ?? ''}
          originalFragment={props.originalFragment}
          selectedText={selectedText}
          onSetBoundary={props.onSetBoundary}
          onCancel={onCancel}
        />
      )}
      {mode === 'add' && props.onAddWord && (
        <AddWordContent
          selectedText={selectedText}
          onAddWord={props.onAddWord}
          onCancel={onCancel}
        />
      )}
    </PopoverShell>
  )
}
