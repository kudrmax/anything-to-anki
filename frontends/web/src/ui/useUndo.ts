import { useCallback, useEffect, useRef, useState } from 'react'
import { OVERLAY } from '../lib/hotkeys'
import { typingIn } from '../lib/typing'

const UNDO_MS = 6000

export interface UndoOffer {
  message: string
  undo: () => Promise<void>
}

/** Последнее действие можно отменить кнопкой в тосте или Cmd-Z, пока тост виден. */
export function useUndo() {
  const [offer, setOffer] = useState<UndoOffer | null>(null)
  const current = useRef<UndoOffer | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const dismiss = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    current.current = null
    setOffer(null)
  }, [])

  const show = useCallback((next: UndoOffer) => {
    if (timer.current) clearTimeout(timer.current)
    current.current = next
    setOffer(next)
    timer.current = setTimeout(dismiss, UNDO_MS)
  }, [dismiss])

  const run = useCallback(async () => {
    const taken = current.current
    if (!taken) return
    dismiss()
    await taken.undo()
  }, [dismiss])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'z' || !(event.metaKey || event.ctrlKey) || event.shiftKey || typingIn(event.target)) return
      if (!current.current || document.querySelector(OVERLAY)) return
      event.preventDefault()
      void run()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [run])

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  return { offer, show, run, dismiss }
}
