import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'

interface SetContextPopoverProps {
  phrase: string
  lemma: string
  position: { x: number; y: number; yBottom: number }
  onSet: (phrase: string) => Promise<void>
  onClose: () => void
}

export function SetContextPopover({ phrase, lemma, position, onSet, onClose }: SetContextPopoverProps) {
  const [loading, setLoading] = useState(false)
  const [flipped, setFlipped] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    if (rect.top < 8) setFlipped(true)
  }, [])

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

  const handleSet = async () => {
    if (loading) return
    setLoading(true)
    try {
      await onSet(phrase)
    } finally {
      setLoading(false)
    }
  }

  const preview = phrase.length > 60 ? phrase.slice(0, 60) + '…' : phrase

  return (
    <div
      ref={ref}
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
        maxWidth: '280px',
      }}
    >
      <p className="text-xs" style={{ color: 'var(--td)' }}>
        Context for: <span className="font-semibold" style={{ color: 'var(--accent)' }}>{lemma}</span>
      </p>
      <p
        className="text-xs italic leading-relaxed"
        style={{ color: 'var(--tm)', borderLeft: '2px solid var(--ag)', paddingLeft: '0.5rem' }}
      >
        "{preview}"
      </p>
      <button
        onClick={() => void handleSet()}
        disabled={loading}
        className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-1 text-xs font-medium text-white disabled:opacity-40 transition-all hover:brightness-110 cursor-pointer self-end"
        style={{ background: 'var(--accent)' }}
      >
        {loading && <Loader2 size={11} className="animate-spin" />}
        Set
      </button>
    </div>
  )
}
