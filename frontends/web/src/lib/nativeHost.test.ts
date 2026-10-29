import { describe, expect, it, vi } from 'vitest'
import { CLOSE_QUICK_ADD_HANDLER, FILE_DROP_EVENT, nativeHost, PICK_FILE_HANDLER, quickAddPanel, THEME_HANDLER, TITLEBAR_HANDLER, windowTheme, windowTitlebar } from './nativeHost'

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

  it('returns the paths of several picked files', async () => {
    const { win, postMessage } = hostWindow(['/a/1.txt', '/a/2.txt', 7])

    expect(await nativeHost(win)?.pickFiles()).toEqual(['/a/1.txt', '/a/2.txt'])
    expect(postMessage).toHaveBeenCalledWith({ multiple: true })
  })

  it('returns no paths when picking several is cancelled', async () => {
    const { win } = hostWindow(null)

    expect(await nativeHost(win)?.pickFiles()).toEqual([])
  })

  it('passes on paths the macOS app reports for dropped files until unsubscribed', () => {
    const target = new EventTarget()
    const win = Object.assign(target, hostWindow(null).win) as unknown as Window
    const listener = vi.fn()

    const unsubscribe = nativeHost(win)?.onFileDrop(listener)
    win.dispatchEvent(new CustomEvent(FILE_DROP_EVENT, { detail: ['/Users/me/a.epub', 42] }))
    unsubscribe?.()
    win.dispatchEvent(new CustomEvent(FILE_DROP_EVENT, { detail: ['/Users/me/b.epub'] }))

    expect(listener).toHaveBeenCalledOnce()
    expect(listener).toHaveBeenCalledWith(['/Users/me/a.epub'])
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


describe('windowTitlebar', () => {
  it('is absent in a plain browser', () => {
    expect(windowTitlebar({} as Window)).toBeNull()
  })

  it('asks the macOS app to drag and to double-click its title bar', () => {
    const postMessage = vi.fn().mockResolvedValue(null)
    const win = { webkit: { messageHandlers: { [TITLEBAR_HANDLER]: { postMessage } } } } as unknown as Window

    windowTitlebar(win)?.drag()
    windowTitlebar(win)?.doubleClick()

    expect(postMessage.mock.calls).toEqual([['drag'], ['doubleClick']])
  })
})

describe('windowTheme', () => {
  it('is absent in a plain browser', () => {
    expect(windowTheme({} as Window)).toBeNull()
  })

  it('tells the macOS app which theme the window follows', () => {
    const postMessage = vi.fn().mockResolvedValue(null)
    const win = { webkit: { messageHandlers: { [THEME_HANDLER]: { postMessage } } } } as unknown as Window

    windowTheme(win)?.follow('system')
    windowTheme(win)?.follow('light')

    expect(postMessage.mock.calls).toEqual([['system'], ['light']])
  })
})
