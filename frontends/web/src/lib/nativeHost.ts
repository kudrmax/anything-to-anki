// Capabilities of the macOS app shell (frontends/macos). Absent in a plain browser.
export const PICK_FILE_HANDLER = 'pickFile'

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
