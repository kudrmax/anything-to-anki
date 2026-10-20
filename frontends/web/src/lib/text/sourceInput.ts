const VIDEO_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov']
const SUBTITLE_EXTENSION = 'srt'
/** Several paths in the Add field: one per line. */
export const PATH_SEPARATOR = '\n'

const extensionOf = (path: string): string => path.split('.').pop()?.toLowerCase() ?? ''

export function isVideoPath(path: string): boolean {
  return VIDEO_EXTENSIONS.includes(extensionOf(path))
}

export interface SourcePaths {
  filePath: string
  srtPath: string
}

/** One dropped video takes one dropped .srt along; a lone .srt dropped onto a chosen video becomes its subtitles;
 *  any other several files are a batch, one path per line. */
export function withDroppedPaths(current: SourcePaths, dropped: readonly string[]): SourcePaths {
  const video = dropped.find(isVideoPath)
  const subtitles = dropped.find(path => extensionOf(path) === SUBTITLE_EXTENSION)
  const pair = dropped.length === 2 && video !== undefined && subtitles !== undefined
  if (pair || (video && dropped.length === 1)) return { filePath: video, srtPath: subtitles ?? '' }
  if (dropped.length > 1) return { filePath: dropped.join(PATH_SEPARATOR), srtPath: '' }
  if (subtitles && dropped.length === 1 && isVideoPath(current.filePath)) return { ...current, srtPath: subtitles }
  return { filePath: dropped[0] ?? current.filePath, srtPath: '' }
}
