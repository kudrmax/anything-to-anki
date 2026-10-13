const VIDEO_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov']
const SUBTITLE_EXTENSION = 'srt'

const extensionOf = (path: string): string => path.split('.').pop()?.toLowerCase() ?? ''

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
