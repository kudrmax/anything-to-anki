// Capabilities of the macOS app shell (frontends/macos). Absent in a plain browser.
export const PICK_FILE_HANDLER = 'pickFile'
export const CLOSE_QUICK_ADD_HANDLER = 'closeQuickAdd'
export const FILE_DROP_EVENT = 'nativefiledrop'

interface ReplyHandler {
  postMessage(body: unknown): Promise<unknown>
}

interface ShellWindow {
  webkit?: { messageHandlers?: Record<string, ReplyHandler | undefined> }
}

export interface NativeHost {
  /** Opens the Finder picker and resolves to the absolute path, or null when cancelled. */
  pickFile(extensions?: readonly string[]): Promise<string | null>
  /** Calls back with absolute paths of files dropped on the page; returns the unsubscribe. */
  onFileDrop(listener: (paths: string[]) => void): () => void
}

const droppedPaths = (event: Event): string[] => {
  const detail: unknown = event instanceof CustomEvent ? event.detail : null
  return Array.isArray(detail) ? detail.filter((path): path is string => typeof path === 'string') : []
}

export function nativeHost(win: Window = window): NativeHost | null {
  const handler = (win as ShellWindow).webkit?.messageHandlers?.[PICK_FILE_HANDLER]
  if (!handler) return null
  return {
    async pickFile(extensions) {
      const path = await handler.postMessage({ extensions })
      return typeof path === 'string' ? path : null
    },
    onFileDrop(listener) {
      const handle = (event: Event) => {
        const paths = droppedPaths(event)
        if (paths.length > 0) listener(paths)
      }
      win.addEventListener(FILE_DROP_EVENT, handle)
      return () => win.removeEventListener(FILE_DROP_EVENT, handle)
    },
  }
}

export interface QuickAddPanel {
  /** Closes the floating Quick Add panel the macOS Services menu opened. */
  close(): void
}

export function quickAddPanel(win: Window = window): QuickAddPanel | null {
  const handler = (win as ShellWindow).webkit?.messageHandlers?.[CLOSE_QUICK_ADD_HANDLER]
  if (!handler) return null
  return {
    close() {
      void handler.postMessage(null)
    },
  }
}
