const VIDEO_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov']

const extensionOf = (path: string): string => path.split('.').pop()?.toLowerCase() ?? ''

export function detectedFileType(path: string): string {
  const ext = extensionOf(path)
  if (ext === 'epub') return 'Book · epub'
  if (VIDEO_EXTENSIONS.includes(ext)) return 'Video · ' + ext
  if (ext === 'srt') return 'Subtitles · srt'
  if (ext === 'html') return 'Article · html'
  return 'Text · ' + (ext || 'txt')
}

export function isVideoPath(path: string): boolean {
  return VIDEO_EXTENSIONS.includes(extensionOf(path))
}

export function detectedUrlType(url: string): string {
  if (url.includes('genius.com')) return 'Lyrics · Genius'
  if (url.includes('youtube.com') || url.includes('youtu.be')) return 'Video · YouTube'
  return 'Article · web'
}
