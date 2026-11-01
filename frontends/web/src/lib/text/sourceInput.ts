import type { FileTypes } from '@/api/types'

/** Several paths in the Add field: one per line. */
export const PATH_SEPARATOR = '\n'
/** Until the backend has told the file types, no file pairs with another. */
export const NO_FILE_TYPES: FileTypes = { video_extensions: [], subtitle_extensions: [] }

const extensionOf = (path: string): string => path.split('.').pop()?.toLowerCase() ?? ''

export interface SourcePaths {
  filePath: string
  srtPath: string
}

/** One dropped video takes one dropped subtitle file along; a lone subtitle file dropped onto a chosen video
 *  becomes its subtitles; any other several files are a batch, one path per line. */
export function withDroppedPaths(current: SourcePaths, dropped: readonly string[], types: FileTypes): SourcePaths {
  const isVideoPath = (path: string) => types.video_extensions.includes(extensionOf(path))
  const video = dropped.find(isVideoPath)
  const subtitles = dropped.find(path => types.subtitle_extensions.includes(extensionOf(path)))
  const pair = dropped.length === 2 && video !== undefined && subtitles !== undefined
  if (pair || (video && dropped.length === 1)) return { filePath: video, srtPath: subtitles ?? '' }
  if (dropped.length > 1) return { filePath: dropped.join(PATH_SEPARATOR), srtPath: '' }
  if (subtitles && dropped.length === 1 && isVideoPath(current.filePath)) return { ...current, srtPath: subtitles }
  return { filePath: dropped[0] ?? current.filePath, srtPath: '' }
}
