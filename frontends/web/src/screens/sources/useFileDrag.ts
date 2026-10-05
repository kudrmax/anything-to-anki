import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

const FILES_TYPE = 'Files'

const carriesFiles = (event: DragEvent): boolean => event.dataTransfer?.types.includes(FILES_TYPE) ?? false

interface FileDragHandlers {
  onEnter: () => void
  /** A drop the page has to handle itself: the browser exposes no file paths, only the macOS app does. */
  onBrowserDrop: () => void
}

/** Tracks a file dragged over the window and lets it be dropped anywhere on the page. */
export function useFileDrag({ onEnter, onBrowserDrop }: FileDragHandlers): { dragging: boolean; reset: () => void } {
  const [dragging, setDragging] = useState(false)
  const depth = useRef(0)
  const handlers = useRef({ onEnter, onBrowserDrop })
  useLayoutEffect(() => {
    handlers.current = { onEnter, onBrowserDrop }
  })

  const reset = useCallback(() => {
    depth.current = 0
    setDragging(false)
  }, [])

  useEffect(() => {
    const enter = (event: DragEvent) => {
      if (!carriesFiles(event)) return
      if (depth.current++ === 0) {
        setDragging(true)
        handlers.current.onEnter()
      }
    }
    const over = (event: DragEvent) => {
      if (!carriesFiles(event)) return
      event.preventDefault()
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
    }
    const leave = (event: DragEvent) => {
      if (!carriesFiles(event)) return
      depth.current = Math.max(0, depth.current - 1)
      if (depth.current === 0) setDragging(false)
    }
    const drop = (event: DragEvent) => {
      if (!carriesFiles(event)) return
      event.preventDefault()
      reset()
      handlers.current.onBrowserDrop()
    }
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragover', over)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', drop)
    return () => {
      window.removeEventListener('dragenter', enter)
      window.removeEventListener('dragover', over)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('drop', drop)
    }
  }, [reset])

  return { dragging, reset }
}
