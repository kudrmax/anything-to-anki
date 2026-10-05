import { describe, expect, it } from 'vitest'
import { withDroppedPaths } from './sourceInput'

const EMPTY = { filePath: '', srtPath: '' }

describe('withDroppedPaths', () => {
  it('takes a dropped file as the source', () => {
    expect(withDroppedPaths(EMPTY, ['/books/novel.epub'])).toEqual({ filePath: '/books/novel.epub', srtPath: '' })
  })

  it('pairs a dropped video with dropped subtitles in any order', () => {
    expect(withDroppedPaths(EMPTY, ['/m/film.srt', '/m/film.mkv'])).toEqual({ filePath: '/m/film.mkv', srtPath: '/m/film.srt' })
  })

  it('adds lone subtitles to the chosen video', () => {
    const current = { filePath: '/m/film.mkv', srtPath: '' }

    expect(withDroppedPaths(current, ['/m/film.srt'])).toEqual({ filePath: '/m/film.mkv', srtPath: '/m/film.srt' })
  })

  it('takes lone subtitles as the source when no video is chosen', () => {
    expect(withDroppedPaths({ filePath: '/books/novel.epub', srtPath: '' }, ['/m/film.srt'])).toEqual({ filePath: '/m/film.srt', srtPath: '' })
  })

  it('drops old subtitles when another file replaces the video', () => {
    const current = { filePath: '/m/film.mkv', srtPath: '/m/film.srt' }

    expect(withDroppedPaths(current, ['/notes/a.txt'])).toEqual({ filePath: '/notes/a.txt', srtPath: '' })
  })
})
