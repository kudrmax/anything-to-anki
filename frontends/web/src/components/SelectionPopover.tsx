import { useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SelectionPopoverProps {
  phrase: string
  position: { x: number; y: number }
  onAdd: (targetTokens: string[], contextFragment: string) => Promise<void>
  onClose: () => void
}

function tokenise(phrase: string): string[] {
  return phrase.split(/\s+/).map(t => t.trim()).filter(Boolean)
}

export function SelectionPopover({ phrase, position, onAdd, onClose }: SelectionPopoverProps) {
  const tokens = tokenise(phrase)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [onClose])

  const toggleToken = (i: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const handleAdd = async () => {
    if (selected.size === 0 || loading) return
    const orderedTokens = tokens.filter((_, i) => selected.has(i))
    setLoading(true)
    try {
      await onAdd(orderedTokens, phrase)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        transform: 'translateX(-50%) translateY(calc(-100% - 8px))',
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
        maxWidth: '320px',
      }}
    >
      <p className="text-xs" style={{ color: 'var(--td)' }}>
        Нажми на слово(а) — target word
      </p>
      <div className="flex flex-wrap gap-1">
        {tokens.map((token, i) => (
          <span
            key={i}
            onClick={() => toggleToken(i)}
            className={cn(
              'cursor-pointer rounded px-1.5 py-0.5 text-sm font-mono transition-all select-none',
              selected.has(i)
                ? 'font-semibold'
                : 'opacity-70 hover:opacity-100',
            )}
            style={{
              color: selected.has(i) ? 'var(--accent)' : 'var(--tm)',
              background: selected.has(i) ? 'var(--abg)' : 'transparent',
              border: selected.has(i) ? '1px solid var(--ag)' : '1px solid transparent',
            }}
          >
            {token}
          </span>
        ))}
      </div>
      <button
        onClick={handleAdd}
        disabled={selected.size === 0 || loading}
        className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-1 text-xs font-medium text-white disabled:opacity-40 transition-all hover:brightness-110 cursor-pointer self-end"
        style={{ background: 'var(--accent)' }}
      >
        {loading && <Loader2 size={11} className="animate-spin" />}
        Add
      </button>
    </div>
  )
}
