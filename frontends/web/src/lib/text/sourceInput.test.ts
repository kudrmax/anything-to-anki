import { describe, expect, it } from 'vitest'
import { NO_FILE_TYPES, withDroppedPaths } from './sourceInput'

const EMPTY = { filePath: '', srtPath: '' }
const TYPES = { video_extensions: ['mkv', 'avi'], subtitle_extensions: ['srt', 'ass'] }

describe('withDroppedPaths', () => {
  it('takes a dropped file as the source', () => {
    expect(withDroppedPaths(EMPTY, ['/books/novel.epub'], TYPES)).toEqual({ filePath: '/books/novel.epub', srtPath: '' })
  })

  it('pairs a dropped video with dropped subtitles in any order', () => {
    expect(withDroppedPaths(EMPTY, ['/m/film.srt', '/m/film.mkv'], TYPES)).toEqual({ filePath: '/m/film.mkv', srtPath: '/m/film.srt' })
  })

  it('pairs a dropped video with subtitles of any subtitle format', () => {
    expect(withDroppedPaths(EMPTY, ['/m/film.avi', '/m/Eng Sub/film.ass'], TYPES)).toEqual({ filePath: '/m/film.avi', srtPath: '/m/Eng Sub/film.ass' })
  })

  it('pairs nothing until the file types are known', () => {
    expect(withDroppedPaths(EMPTY, ['/m/film.srt', '/m/film.mkv'], NO_FILE_TYPES)).toEqual({ filePath: '/m/film.srt\n/m/film.mkv', srtPath: '' })
  })

  it('adds lone subtitles to the chosen video', () => {
    const current = { filePath: '/m/film.mkv', srtPath: '' }

    expect(withDroppedPaths(current, ['/m/film.srt'], TYPES)).toEqual({ filePath: '/m/film.mkv', srtPath: '/m/film.srt' })
  })

  it('takes lone subtitles as the source when no video is chosen', () => {
    expect(withDroppedPaths({ filePath: '/books/novel.epub', srtPath: '' }, ['/m/film.srt'], TYPES)).toEqual({ filePath: '/m/film.srt', srtPath: '' })
  })

  it('drops old subtitles when another file replaces the video', () => {
    const current = { filePath: '/m/film.mkv', srtPath: '/m/film.srt' }

    expect(withDroppedPaths(current, ['/notes/a.txt'], TYPES)).toEqual({ filePath: '/notes/a.txt', srtPath: '' })
  })

  it('takes several dropped files as a batch, one path per line', () => {
    expect(withDroppedPaths(EMPTY, ['/a/1.txt', '/a/2.txt', '/a/3.md'], TYPES)).toEqual({ filePath: '/a/1.txt\n/a/2.txt\n/a/3.md', srtPath: '' })
  })

  it('takes several videos with subtitles as a batch, not a pair', () => {
    expect(withDroppedPaths(EMPTY, ['/m/a.mkv', '/m/a.srt', '/m/b.mkv'], TYPES)).toEqual({ filePath: '/m/a.mkv\n/m/a.srt\n/m/b.mkv', srtPath: '' })
  })
})
