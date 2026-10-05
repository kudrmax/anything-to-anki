const VIDEO_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov']
const SUBTITLE_EXTENSION = 'srt'

const extensionOf = (path: string): string => path.split('.').pop()?.toLowerCase() ?? ''

export function detectedFileType(path: string): string {
  const ext = extensionOf(path)
  if (ext === 'epub') return 'Book · epub'
  if (VIDEO_EXTENSIONS.includes(ext)) return 'Video · ' + ext
  if (ext === SUBTITLE_EXTENSION) return 'Subtitles · srt'
  if (ext === 'html') return 'Article · html'
  return 'Text · ' + (ext || 'txt')
}

export function isVideoPath(path: string): boolean {
  return VIDEO_EXTENSIONS.includes(extensionOf(path))
}

export interface SourcePaths {
  filePath: string
  srtPath: string
}

/** A dropped video takes a dropped .srt along; a lone .srt dropped onto a chosen video becomes its subtitles. */
export function withDroppedPaths(current: SourcePaths, dropped: readonly string[]): SourcePaths {
  const video = dropped.find(isVideoPath)
  const subtitles = dropped.find(path => extensionOf(path) === SUBTITLE_EXTENSION)
  if (video) return { filePath: video, srtPath: subtitles ?? '' }
  if (subtitles && dropped.length === 1 && isVideoPath(current.filePath)) return { ...current, srtPath: subtitles }
  return { filePath: dropped[0] ?? current.filePath, srtPath: '' }
}

export function detectedUrlType(url: string): string {
  if (url.includes('genius.com')) return 'Lyrics · Genius'
  if (url.includes('youtube.com') || url.includes('youtu.be')) return 'Video · YouTube'
  return 'Article · web'
}
