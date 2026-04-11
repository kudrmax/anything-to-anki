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

function computeDiff(original: string, updated: string, _lemma: string): DiffSegment[] {
  // Word-level diff using longest common subsequence (LCS).
  // Split into words, find LCS, then mark words as same/added/removed.
  const oldWords = original.split(/(\s+)/) // keep whitespace as separate tokens
  const newWords = updated.split(/(\s+)/)

  // Filter to non-empty tokens for LCS, but track whitespace
  const oldTokens = oldWords.filter(w => w.length > 0)
  const newTokens = newWords.filter(w => w.length > 0)

  // Build LCS table on non-whitespace words only
  const oldW = oldTokens.filter(w => w.trim().length > 0)
  const newW = newTokens.filter(w => w.trim().length > 0)

  const m = oldW.length
  const n = newW.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = oldW[i - 1] === newW[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  // Backtrack to find which words are in LCS
  const oldInLcs = new Set<number>()
  const newInLcs = new Set<number>()
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (oldW[i - 1] === newW[j - 1]) {
      oldInLcs.add(i - 1)
      newInLcs.add(j - 1)
      i--; j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }

  // Build segments: walk through new words, interleave with removed old words
  const segments: DiffSegment[] = []
  let oldIdx = 0
  let newIdx = 0

  const pushSegment = (text: string, type: DiffSegment['type']) => {
    if (!text) return
    const last = segments[segments.length - 1]
    if (last && last.type === type) {
      last.text += text
    } else {
      segments.push({ text, type })
    }
  }

  while (oldIdx < oldW.length || newIdx < newW.length) {
    if (oldIdx < oldW.length && oldInLcs.has(oldIdx) && newIdx < newW.length && newInLcs.has(newIdx)) {
      // Both in LCS — same word
      pushSegment(newW[newIdx], 'same')
      oldIdx++
      newIdx++
      // Add space after if not last
      if (newIdx < newW.length) pushSegment(' ', 'same')
    } else if (oldIdx < oldW.length && !oldInLcs.has(oldIdx)) {
      // Old word not in LCS — removed
      pushSegment(oldW[oldIdx], 'removed')
      oldIdx++
      if (oldIdx < oldW.length || newIdx < newW.length) pushSegment(' ', 'removed')
    } else if (newIdx < newW.length && !newInLcs.has(newIdx)) {
      // New word not in LCS — added
      pushSegment(newW[newIdx], 'added')
      newIdx++
      if (newIdx < newW.length) pushSegment(' ', 'added')
    } else {
      break
    }
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
                  color: 'var(--error)',
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
                style={{ color: 'var(--status-learn)' }}
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
              background: selected.has(i) ? 'var(--abg)' : 'transparent',
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

  if (mode === 'edit' && (!props.lemma || !props.originalFragment || !props.onSetBoundary)) return null
  if (mode === 'add' && !props.onAddWord) return null

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
