// Capabilities of the macOS app shell (frontends/macos). Absent in a plain browser.
export const PICK_FILE_HANDLER = 'pickFile'
export const CLOSE_QUICK_ADD_HANDLER = 'closeQuickAdd'

interface ReplyHandler {
  postMessage(body: unknown): Promise<unknown>
}

interface ShellWindow {
  webkit?: { messageHandlers?: Record<string, ReplyHandler | undefined> }
}

export interface NativeHost {
  /** Opens the Finder picker and resolves to the absolute path, or null when cancelled. */
  pickFile(extensions?: readonly string[]): Promise<string | null>
}

export function nativeHost(win: Window = window): NativeHost | null {
  const handler = (win as ShellWindow).webkit?.messageHandlers?.[PICK_FILE_HANDLER]
  if (!handler) return null
  return {
    async pickFile(extensions) {
      const path = await handler.postMessage({ extensions })
      return typeof path === 'string' ? path : null
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
