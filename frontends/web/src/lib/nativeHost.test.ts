import { describe, expect, it, vi } from 'vitest'
import { CLOSE_QUICK_ADD_HANDLER, nativeHost, PICK_FILE_HANDLER, quickAddPanel } from './nativeHost'

const hostWindow = (reply: unknown) => {
  const postMessage = vi.fn().mockResolvedValue(reply)
  return { win: { webkit: { messageHandlers: { [PICK_FILE_HANDLER]: { postMessage } } } } as unknown as Window, postMessage }
}

describe('nativeHost', () => {
  it('is absent in a plain browser', () => {
    expect(nativeHost({} as Window)).toBeNull()
  })

  it('returns the path the macOS app picked', async () => {
    const { win, postMessage } = hostWindow('/Users/me/Movies/film.mkv')

    const path = await nativeHost(win)?.pickFile(['srt'])

    expect(path).toBe('/Users/me/Movies/film.mkv')
    expect(postMessage).toHaveBeenCalledWith({ extensions: ['srt'] })
  })

  it('returns null when the picker is cancelled', async () => {
    const { win } = hostWindow(null)

    expect(await nativeHost(win)?.pickFile()).toBeNull()
  })
})

describe('quickAddPanel', () => {
  it('is absent outside the Quick Add panel', () => {
    expect(quickAddPanel({} as Window)).toBeNull()
  })

  it('asks the macOS app to close the panel', () => {
    const postMessage = vi.fn().mockResolvedValue(null)
    const win = { webkit: { messageHandlers: { [CLOSE_QUICK_ADD_HANDLER]: { postMessage } } } } as unknown as Window

    quickAddPanel(win)?.close()

    expect(postMessage).toHaveBeenCalledWith(null)
  })
})
