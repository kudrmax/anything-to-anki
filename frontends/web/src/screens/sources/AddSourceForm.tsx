import { useState } from 'react'
import { api } from '@/api/client'
import type { AudioTrack, SourceSummary, SourceType, SubtitleTrack } from '@/api/types'
import { detectedFileType, detectedUrlType, isVideoPath } from '@/lib/text/sourceInput'
import { Button, Field, Label, Segmented, Stack, Tabs, Text, TextArea } from '@/ui'
import { PathField } from './PathField'
import { TrackSelectionModal } from './TrackSelectionModal'

type Tab = 'text' | 'url' | 'file'
type TextType = 'text_pasted' | 'lyrics_pasted' | 'subtitles_file'

const TABS: { value: Tab; label: string }[] = [
  { value: 'text', label: 'Text' },
  { value: 'url', label: 'URL' },
  { value: 'file', label: 'File' },
]
const TEXT_TYPES: { value: TextType; label: string }[] = [
  { value: 'text_pasted', label: 'Text' },
  { value: 'lyrics_pasted', label: 'Lyrics' },
  { value: 'subtitles_file', label: 'Subtitles' },
]
const TEXT_PLACEHOLDER: Record<TextType, string> = {
  text_pasted: 'Paste text here…',
  lyrics_pasted: 'Paste song lyrics here…',
  subtitles_file: 'Paste .srt subtitle content here…',
}
const SUBTITLE_EXTENSIONS = ['srt']
const NO_SUBTITLES_ERROR = 'subtitles_not_available'
const PREVIEW_LENGTH = 100

interface PendingTracks {
  filePath: string
  srtPath: string
  subtitleTracks: SubtitleTrack[]
  audioTracks: AudioTrack[]
}

interface AddSourceFormProps {
  onCreated: (source: SourceSummary) => void
  onReload: () => Promise<void>
  onToast: (message: string) => void
}

const messageOf = (e: unknown): string => (e instanceof Error ? e.message : String(e))

export function AddSourceForm({ onCreated, onReload, onToast }: AddSourceFormProps) {
  const [tab, setTab] = useState<Tab>('text')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [textType, setTextType] = useState<TextType | null>(null)
  const [url, setUrl] = useState('')
  const [filePath, setFilePath] = useState('')
  const [srtPath, setSrtPath] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingTracks, setPendingTracks] = useState<PendingTracks | null>(null)

  const addUrl = async () => {
    if (!url.trim()) { setError('Please enter a URL'); return }
    setAdding(true)
    try {
      await api.createUrlSource(url.trim(), title.trim() || undefined)
      await onReload()
      setUrl('')
      setTitle('')
    } catch (e) {
      const message = messageOf(e)
      if (message.includes(NO_SUBTITLES_ERROR)) onToast('Subtitles are not available for this video')
      else setError(message)
    } finally {
      setAdding(false)
    }
  }

  const addFile = async () => {
    if (!filePath.trim()) { setError('Enter file path'); return }
    setAdding(true)
    try {
      const result = await api.createFileSource(filePath.trim(), srtPath.trim() || undefined, title.trim() || undefined, undefined, undefined)
      if (result.status === 'track_selection_required') {
        setPendingTracks({
          filePath: result.file_path ?? filePath.trim(),
          srtPath: result.srt_path ?? srtPath.trim(),
          subtitleTracks: result.subtitle_tracks ?? [],
          audioTracks: result.audio_tracks ?? [],
        })
      } else if (result.id) {
        setFilePath('')
        setSrtPath('')
        setTitle('')
        await onReload()
      }
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setAdding(false)
    }
  }

  const confirmTracks = async (subtitleIndex: number | undefined, audioIndex: number | undefined) => {
    if (!pendingTracks) return
    const pending = pendingTracks
    setPendingTracks(null)
    setAdding(true)
    try {
      const result = await api.createFileSource(pending.filePath, pending.srtPath || undefined, title.trim() || undefined, subtitleIndex, audioIndex)
      if (result.id) {
        setFilePath('')
        setSrtPath('')
        setTitle('')
        await onReload()
      }
    } catch (e) {
      onToast(messageOf(e))
    } finally {
      setAdding(false)
    }
  }

  const addText = async () => {
    if (!text.trim()) return
    if (!textType) { setError('Select source type'); return }
    setAdding(true)
    try {
      const created = await api.createSource(text.trim(), textType as SourceType, title.trim() || undefined)
      onCreated({
        id: created.id,
        title: title.trim() || text.trim().slice(0, PREVIEW_LENGTH),
        raw_text_preview: text.trim().slice(0, PREVIEW_LENGTH),
        status: 'new',
        source_type: textType,
        content_type: textType === 'lyrics_pasted' ? 'lyrics' : 'text',
        source_url: null,
        video_downloaded: false,
        created_at: new Date().toISOString(),
        candidate_count: 0,
        learn_count: 0,
        processing_stage: null,
        collection_id: null,
        collection_name: null,
      })
      setText('')
      setTextType(null)
      setTitle('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add source')
    } finally {
      setAdding(false)
    }
  }

  const add = () => {
    setError(null)
    if (tab === 'url') void addUrl()
    else if (tab === 'file') void addFile()
    else void addText()
  }

  return (
    <>
      <Tabs value={tab} options={TABS} onChange={setTab} />
      <Stack gap="m">
        <Stack>
          <Field value={title} placeholder="Title (optional)" onChange={e => setTitle(e.target.value)} />
          {tab === 'text' && (
            <TextArea value={text} placeholder={TEXT_PLACEHOLDER[textType ?? 'text_pasted']} onChange={e => setText(e.target.value)} />
          )}
          {tab === 'url' && (
            <>
              <Field value={url} placeholder="https://genius.com/… or youtube.com/…" onChange={e => setUrl(e.target.value)} />
              {url.trim() && <Text tone="muted" size="s">{detectedUrlType(url)}</Text>}
            </>
          )}
          {tab === 'file' && (
            <>
              <PathField value={filePath} placeholder="/path/to/movie.mkv" onChange={setFilePath} />
              {isVideoPath(filePath) && (
                <PathField value={srtPath} placeholder="/path/to/subtitles.srt (optional)" extensions={SUBTITLE_EXTENSIONS} onChange={setSrtPath} />
              )}
              {filePath.trim() && <Text tone="muted" size="s">{detectedFileType(filePath)}</Text>}
            </>
          )}
        </Stack>
        {tab === 'text' && (
          <div>
            <Label flush>Source type</Label>
            <Segmented value={textType ?? ('' as TextType)} options={TEXT_TYPES} onChange={setTextType} />
          </div>
        )}
        {error && <Text tone="err" size="s">{error}</Text>}
        <Button variant="fill" wide busy={adding} onClick={add}>Add source</Button>
      </Stack>
      {pendingTracks && (
        <TrackSelectionModal
          subtitleTracks={pendingTracks.subtitleTracks}
          audioTracks={pendingTracks.audioTracks}
          onCancel={() => setPendingTracks(null)}
          onConfirm={confirmTracks}
        />
      )}
    </>
  )
}
