import { useCallback, useEffect, useRef, useState } from 'react'
import type { JSX } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Link, File, Loader2, Plus, RefreshCw } from 'lucide-react'
import { api } from '@/api/client'
import type { AudioTrack, Collection, SourceSummary, SourceType, Stats, SubtitleTrack } from '@/api/types'
import { SourceCard } from '@/components/SourceCard'
import { ReprocessModal } from '@/components/ReprocessModal'
import { useSourcePolling } from '@/hooks/useSourcePolling'

function detectedFileType(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'epub') return 'Book · epub'
  if (['mp4', 'mkv', 'avi', 'mov'].includes(ext)) return 'Video · ' + ext
  if (ext === 'srt') return 'Subtitles · srt'
  if (ext === 'html') return 'Article · html'
  return 'Text · ' + (ext || 'txt')
}

function isVideoPath(path: string): boolean {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  return ['mp4', 'mkv', 'avi', 'mov'].includes(ext)
}

function StatWidget({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass-card rounded-2xl flex flex-col items-center justify-center py-4 px-2 text-center">
      <div className="text-3xl font-bold grad-text leading-none">{value}</div>
      <div className="text-[11px] font-medium mt-1.5" style={{ color: 'var(--tm)' }}>{label}</div>
    </div>
  )
}

function ProgressCard({
  cefrLevel,
  learnCount,
  candidateCount,
}: {
  cefrLevel: string
  learnCount: number
  candidateCount: number
}) {
  const pct = candidateCount > 0 ? Math.round((learnCount / candidateCount) * 100) : 0
  return (
    <div className="glass-card rounded-2xl px-5 py-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{cefrLevel} progress</span>
        <span className="text-xs" style={{ color: 'var(--tm)' }}>{pct}%</span>
      </div>
      <div className="h-[5px] rounded-full overflow-hidden" style={{ background: 'var(--glass-b)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: 'var(--grad)' }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs" style={{ color: 'var(--tm)' }}>
          {candidateCount} total · {learnCount} to learn
        </span>
        <span className="text-sm font-bold grad-text">{cefrLevel}</span>
      </div>
    </div>
  )
}

export function InboxPage() {
  const navigate = useNavigate()
  const [sources, setSources] = useState<SourceSummary[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [title, setTitle] = useState('')
  const [activeTab, setActiveTab] = useState<'text' | 'url' | 'file'>('text')
  const [textInput, setTextInput] = useState('')
  const [textSourceType, setTextSourceType] = useState<SourceType | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [filePath, setFilePath] = useState('')
  const [srtPath, setSrtPath] = useState('')
  const [pendingFilePath, setPendingFilePath] = useState('')
  const [pendingSrtPath, setPendingSrtPath] = useState('')
  const [adding, setAdding] = useState(false)
  const [processingAll, setProcessingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ text: string; key: number } | null>(null)
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set())
  const processingIdsRef = useRef(processingIds)
  processingIdsRef.current = processingIds
  const [cefrLevel, setCefrLevel] = useState('B2')
  const [subtitleTracks, setSubtitleTracks] = useState<SubtitleTrack[]>([])
  const [audioTracks, setAudioTracks] = useState<AudioTrack[]>([])
  const [selectedSubtitleIndex, setSelectedSubtitleIndex] = useState<number | null>(null)
  const [selectedAudioIndex, setSelectedAudioIndex] = useState<number | null>(null)
  const [showTrackModal, setShowTrackModal] = useState(false)
  const [reprocessSourceId, setReprocessSourceId] = useState<number | null>(null)
  const [collections, setCollections] = useState<Collection[]>([])
  const [activeCollectionId, setActiveCollectionId] = useState<number | null>(null)
  const [newCollectionName, setNewCollectionName] = useState('')
  const [isCreatingCollection, setIsCreatingCollection] = useState(false)
  const [renamingCollectionId, setRenamingCollectionId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [contextMenu, setContextMenu] = useState<{ id: number; x: number; y: number } | null>(null)

  const loadSources = useCallback(async () => {
    try {
      const [list, s, colls] = await Promise.all([
        api.listSources(),
        api.getStats(),
        api.listCollections(),
      ])
      setSources(list)
      setStats(s)
      setCollections(colls)
    } catch {
      // ignore background reload errors
    }
  }, [])

  const filteredSources = activeCollectionId === null
    ? sources
    : sources.filter((s) => s.collection_id === activeCollectionId)

  const handleCreateCollection = async () => {
    const name = newCollectionName.trim()
    if (!name) return
    try {
      await api.createCollection(name)
      setNewCollectionName('')
      setIsCreatingCollection(false)
      void loadSources()
    } catch {
      // ignore
    }
  }

  const handleRenameCollection = async (id: number) => {
    const name = renameValue.trim()
    if (!name) return
    try {
      await api.renameCollection(id, name)
      setRenamingCollectionId(null)
      setContextMenu(null)
      void loadSources()
    } catch {
      // ignore
    }
  }

  const handleDeleteCollection = async (id: number) => {
    const coll = collections.find((c) => c.id === id)
    if (!coll) return
    if (!confirm(`Delete "${coll.name}"? The ${coll.source_count} source(s) will become uncategorized.`)) return
    try {
      await api.deleteCollection(id)
      if (activeCollectionId === id) setActiveCollectionId(null)
      setContextMenu(null)
      void loadSources()
    } catch {
      // ignore
    }
  }

  const handleContextMenu = (e: React.MouseEvent, id: number) => {
    e.preventDefault()
    setContextMenu({ id, x: e.clientX, y: e.clientY })
  }

  const handleAssignCollection = async (sourceId: number, collectionId: number | null) => {
    try {
      await api.assignSourceCollection(sourceId, collectionId)
      void loadSources()
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (!contextMenu) return
    const close = () => setContextMenu(null)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [contextMenu])

  useEffect(() => {
    void loadSources()
    void api.getSettings().then((s) => setCefrLevel(s.cefr_level)).catch(() => {})
  }, [loadSources])

  const handleDone = useCallback(
    (updated: SourceSummary) => {
      setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
      setProcessingIds((prev) => {
        const next = new Set(prev)
        next.delete(updated.id)
        return next
      })
      void api.getStats().then(setStats).catch(() => undefined)
    },
    [],
  )

  const { start: startPolling } = useSourcePolling(null, handleDone)

  const handleAdd = async () => {
    setError(null)

    if (activeTab === 'url') {
      if (!urlInput.trim()) {
        setError('Please enter a URL')
        return
      }
      setAdding(true)
      try {
        const result = await api.createUrlSource(urlInput.trim(), title.trim() || undefined)
        await loadSources()
        setUrlInput('')
        setTitle('')
        startPolling(result.id)
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e)
        if (msg.includes('subtitles_not_available')) {
          setToast({ text: 'Субтитры для видео не получилось получить', key: Date.now() })
        } else {
          setError(msg)
        }
      } finally {
        setAdding(false)
      }
      return
    }

    if (activeTab === 'file') {
      if (!filePath.trim()) {
        setError('Enter file path')
        return
      }
      setAdding(true)
      try {
        const result = await api.createFileSource(
          filePath.trim(),
          srtPath.trim() || undefined,
          title.trim() || undefined,
          undefined,
          undefined,
        )
        if (result.status === 'track_selection_required') {
          setPendingFilePath(result.file_path ?? filePath.trim())
          setPendingSrtPath(result.srt_path ?? srtPath.trim())
          setSubtitleTracks(result.subtitle_tracks ?? [])
          setAudioTracks(result.audio_tracks ?? [])
          setSelectedSubtitleIndex(result.subtitle_tracks?.[0]?.index ?? null)
          setSelectedAudioIndex(result.audio_tracks?.[0]?.index ?? null)
          setShowTrackModal(true)
        } else if (result.id) {
          setFilePath('')
          setSrtPath('')
          setTitle('')
          await loadSources()
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e)
        setError(msg)
      } finally {
        setAdding(false)
      }
      return
    }

    if (!textInput.trim()) return
    if (!textSourceType) {
      setError('Select source type')
      return
    }

    setAdding(true)
    try {
      const created = await api.createSource(textInput.trim(), textSourceType, title.trim() || undefined)
      const resolvedTitle = title.trim() || textInput.trim().slice(0, 100)
      const newSource: SourceSummary = {
        id: created.id,
        title: resolvedTitle,
        raw_text_preview: textInput.trim().slice(0, 100),
        status: 'new',
        source_type: textSourceType,
        content_type: textSourceType === 'lyrics_pasted' ? 'lyrics' : 'text',
        source_url: null,
        video_downloaded: false,
        created_at: new Date().toISOString(),
        candidate_count: 0,
        learn_count: 0,
        processing_stage: null,
        collection_id: null,
        collection_name: null,
      }
      setTextInput('')
      setTextSourceType(null)
      setTitle('')
      setSources((prev) => [newSource, ...prev])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add source')
    } finally {
      setAdding(false)
    }
  }

  const handleProcess = async (id: number) => {
    try {
      await api.processSource(id)
      setSources((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'processing' as const } : s)),
      )
      setProcessingIds((prev) => new Set(prev).add(id))
      startPolling(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start processing')
    }
  }

  const handleProcessAll = async () => {
    const pending = sources.filter((s) => s.status === 'new' || s.status === 'error')
    if (pending.length === 0) return
    setProcessingAll(true)
    try {
      for (const source of pending) {
        try {
          await api.processSource(source.id)
          setSources((prev) =>
            prev.map((s) => (s.id === source.id ? { ...s, status: 'processing' as const } : s)),
          )
          setProcessingIds((prev) => new Set(prev).add(source.id))
          startPolling(source.id)
        } catch {
          // skip individual errors, continue with others
        }
      }
    } finally {
      setProcessingAll(false)
    }
  }

  const handleReview = (id: number) => navigate(`/sources/${id}/review`)
  const handleExport = (id: number) => navigate(`/sources/${id}/export`)

  const handleReprocessClick = (sourceId: number) => {
    const source = sources.find(s => s.id === sourceId)
    if (source?.status === 'error') {
      api.reprocessSource(sourceId)
        .then(() => loadSources())
        .catch((e: Error) => console.error('Reprocess failed:', e))
      return
    }
    setReprocessSourceId(sourceId)
  }

  const handleReprocessConfirm = () => {
    if (reprocessSourceId == null) return
    api.reprocessSource(reprocessSourceId)
      .then(() => { setReprocessSourceId(null); void loadSources() })
      .catch((e: Error) => console.error('Reprocess failed:', e))
  }

  const handleRename = async (id: number, newTitle: string) => {
    try {
      await api.renameSource(id, newTitle)
      setSources((prev) => prev.map((s) => (s.id === id ? { ...s, title: newTitle } : s)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to rename source')
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this source and all its candidates?')) return
    try {
      await api.deleteSource(id)
      setSources((prev) => prev.filter((s) => s.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete source')
    }
  }

  const handleConfirmTracks = async () => {
    if (!pendingFilePath) return
    if (subtitleTracks.length > 0 && selectedSubtitleIndex === null) return
    if (audioTracks.length > 0 && selectedAudioIndex === null) return
    setShowTrackModal(false)
    setAdding(true)
    try {
      const result = await api.createFileSource(
        pendingFilePath,
        pendingSrtPath || undefined,
        title.trim() || undefined,
        subtitleTracks.length > 0 ? selectedSubtitleIndex ?? undefined : undefined,
        audioTracks.length > 0 ? selectedAudioIndex ?? undefined : undefined,
      )
      if (result.id) {
        setFilePath('')
        setSrtPath('')
        setTitle('')
        setPendingFilePath('')
        setPendingSrtPath('')
        setSubtitleTracks([])
        setAudioTracks([])
        await loadSources()
      }
    } catch (e: unknown) {
      setToast({ text: e instanceof Error ? e.message : String(e), key: Date.now() })
    } finally {
      setAdding(false)
    }
  }

  const handleCancelTrackSelection = () => {
    setShowTrackModal(false)
    setPendingFilePath('')
    setPendingSrtPath('')
    setSubtitleTracks([])
    setAudioTracks([])
    setSelectedSubtitleIndex(null)
    setSelectedAudioIndex(null)
  }

  const pendingCount = sources.filter((s) => s.status === 'new' || s.status === 'error').length

  const urlDetectedType =
    urlInput.includes('genius.com')
      ? 'Lyrics · Genius'
      : urlInput.includes('youtube.com') || urlInput.includes('youtu.be')
        ? 'Video · YouTube'
        : 'Article · web'

  return (
    <div className="flex-1 overflow-y-auto">
      <main className="mx-auto max-w-6xl px-4 py-8 grid grid-cols-1 gap-8 lg:grid-cols-[400px_1fr]">
        {/* ── LEFT COLUMN: FORM ── */}
        <section
          className="flex flex-col gap-4"
        >
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
            Add source
          </h2>

          <div className="flex flex-col gap-3 glass-card rounded-2xl p-4">

            {/* Title — always visible, above tabs */}
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title (optional)"
              className="w-full rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
              style={{ background: 'var(--ibg)', border: '1.5px solid var(--ib)', color: 'var(--text)' }}
            />

            {/* Tabs */}
            <div className="glass-pill-group w-fit">
              {(['text', 'url', 'file'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className="flex items-center gap-1.5 cursor-pointer"
                  style={
                    activeTab === tab
                      ? { background: 'var(--accent)', color: '#fff', boxShadow: '0 2px 8px var(--ag)', borderRadius: 'var(--pill-radius, 980px)' }
                      : { color: 'var(--tm)' }
                  }
                >
                  {tab === 'text' && <FileText size={11} />}
                  {tab === 'url'  && <Link size={11} />}
                  {tab === 'file' && <File size={11} />}
                  {tab === 'text' ? 'Text' : tab === 'url' ? 'URL' : 'File'}
                </button>
              ))}
            </div>

            {/* ── TEXT TAB ── */}
            {activeTab === 'text' && (
              <div className="flex flex-col gap-2.5">
                <div className="flex flex-col gap-1.5">
                  <span className="text-[11px]" style={{ color: 'var(--td)' }}>Source type</span>
                  <div className="flex gap-1.5 flex-wrap">
                    {(['text_pasted', 'lyrics_pasted', 'subtitles_file'] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setTextSourceType(t)}
                        className="glass-pill text-[11px] font-medium capitalize cursor-pointer"
                        style={
                          textSourceType === t
                            ? { background: 'var(--accent)', color: '#fff' }
                            : { color: 'var(--tm)' }
                        }
                      >
                        {t === 'text_pasted' ? 'text' : t === 'lyrics_pasted' ? 'lyrics' : 'subtitles'}
                      </button>
                    ))}
                  </div>
                </div>
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder={
                    textSourceType === 'lyrics_pasted'
                      ? 'Paste song lyrics here…'
                      : textSourceType === 'subtitles_file'
                        ? 'Paste .srt subtitle content here…'
                        : 'Paste text here…'
                  }
                  rows={7}
                  className="w-full rounded-lg px-4 py-3 text-sm resize-none transition-colors cosmic-input"
                  style={{ background: 'var(--ibg)', border: '1.5px solid var(--ib)', color: 'var(--text)' }}
                />
              </div>
            )}

            {/* ── URL TAB ── */}
            {activeTab === 'url' && (
              <div className="flex flex-col gap-2.5">
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://genius.com/… or youtube.com/…"
                  className="w-full rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
                  style={{ background: 'var(--ibg)', border: '1.5px solid var(--ib)', color: 'var(--text)' }}
                />
                {urlInput.trim() && (
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full"
                      style={{
                        background: 'var(--abg)',
                        border: '1px solid var(--ag)',
                        color: 'var(--accent)',
                      }}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--accent)' }} />
                      {urlDetectedType}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* ── FILE TAB ── */}
            {activeTab === 'file' && (
              <div className="flex flex-col gap-2.5">
                <input
                  type="text"
                  value={filePath}
                  onChange={(e) => { setFilePath(e.target.value); setError(null) }}
                  placeholder="/path/to/movie.mkv"
                  className="w-full rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
                  style={{ background: 'var(--ibg)', border: '1.5px solid var(--ib)', color: 'var(--text)' }}
                />
                {filePath.trim() && isVideoPath(filePath.trim()) && (
                  <input
                    type="text"
                    value={srtPath}
                    onChange={(e) => setSrtPath(e.target.value)}
                    placeholder="/path/to/subtitles.srt (optional)"
                    className="w-full rounded-lg px-4 py-2.5 text-sm transition-colors cosmic-input"
                    style={{ background: 'var(--ibg)', border: '1.5px solid var(--ib)', color: 'var(--text)' }}
                  />
                )}
                {filePath.trim() && (
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full"
                      style={{
                        background: 'var(--abg)',
                        border: '1px solid var(--ag)',
                        color: 'var(--accent)',
                      }}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--accent)' }} />
                      {detectedFileType(filePath.trim())}
                    </span>
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-xs" style={{ color: 'var(--error)' }}>{error}</p>}

            <button
              onClick={() => void handleAdd()}
              disabled={adding}
              className="glass-pill glass-pill-prominent flex items-center justify-center gap-2 text-sm font-medium text-white disabled:opacity-50 cursor-pointer hover:-translate-y-px"
              style={{ background: 'var(--accent)', boxShadow: '0 4px 14px var(--ag)', color: '#fff' }}
            >
              {adding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              Add source
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-2">
            <StatWidget label="To learn" value={sources.reduce((s, r) => s + r.learn_count, 0)} />
            <StatWidget label="Candidates" value={sources.reduce((s, r) => s + r.candidate_count, 0)} />
            <StatWidget label="Sources" value={sources.length} />
          </div>

          {/* Progress */}
          <ProgressCard
            cefrLevel={cefrLevel}
            learnCount={sources.reduce((s, r) => s + r.learn_count, 0)}
            candidateCount={sources.reduce((s, r) => s + r.candidate_count, 0)}
          />
        </section>

        {/* ── RIGHT COLUMN: SOURCE LIST ── */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
                Sources{sources.length > 0 && <span className="ml-2" style={{ color: 'var(--td)' }}>({sources.length})</span>}
              </h2>
              {stats && (
                <span className="text-xs">
                  {stats.learn_count > 0 && (
                    <span style={{ color: 'var(--accent)' }}>{stats.learn_count} to learn</span>
                  )}
                  {stats.learn_count > 0 && stats.known_word_count > 0 && (
                    <span style={{ color: 'var(--td)' }}> · </span>
                  )}
                  {stats.known_word_count > 0 && (
                    <span style={{ color: 'var(--td)' }}>{stats.known_word_count} known</span>
                  )}
                </span>
              )}
            </div>
            {pendingCount > 0 && (
              <button
                onClick={() => void handleProcessAll()}
                disabled={processingAll}
                className="glass-pill flex items-center gap-1.5 text-xs font-medium disabled:opacity-50 cursor-pointer"
                style={{ color: 'var(--tm)' }}
              >
                {processingAll
                  ? <Loader2 size={11} className="animate-spin" />
                  : <RefreshCw size={11} />
                }
                Process all ({pendingCount})
              </button>
            )}
          </div>

          {/* Collection filter chips */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <button
              className="glass-pill text-xs cursor-pointer transition-colors"
              style={{
                background: activeCollectionId === null ? 'var(--abg)' : undefined,
                color: activeCollectionId === null ? 'var(--accent)' : 'var(--tm)',
                border: activeCollectionId === null ? '1px solid var(--accent)' : '1px solid var(--glass-b)',
              }}
              onClick={() => setActiveCollectionId(null)}
            >
              All
            </button>
            {collections.map((c) => (
              <button
                key={c.id}
                className="glass-pill text-xs cursor-pointer transition-colors"
                style={{
                  background: activeCollectionId === c.id ? 'var(--abg)' : undefined,
                  color: activeCollectionId === c.id ? 'var(--accent)' : 'var(--tm)',
                  border: activeCollectionId === c.id ? '1px solid var(--accent)' : '1px solid var(--glass-b)',
                }}
                onClick={() => setActiveCollectionId(c.id)}
                onContextMenu={(e) => handleContextMenu(e, c.id)}
              >
                {c.name} ({c.source_count})
              </button>
            ))}
            {isCreatingCollection ? (
              <div className="flex items-center gap-1.5">
                <input
                  autoFocus
                  className="glass-pill text-xs px-3 py-1.5 outline-none"
                  style={{ background: 'var(--surface-menu)', color: 'var(--text)', border: '1px solid var(--accent)', width: '160px' }}
                  placeholder="Collection name…"
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleCreateCollection()
                    if (e.key === 'Escape') { setIsCreatingCollection(false); setNewCollectionName('') }
                  }}
                />
                <button className="glass-pill text-xs cursor-pointer" style={{ background: 'var(--abg)', color: 'var(--accent)', border: '1px solid var(--accent)' }} onClick={() => void handleCreateCollection()}>Create</button>
                <button className="glass-pill text-xs cursor-pointer" style={{ color: 'var(--tm)', border: '1px solid var(--glass-b)' }} onClick={() => { setIsCreatingCollection(false); setNewCollectionName('') }}>Cancel</button>
              </div>
            ) : (
              <button className="glass-pill text-xs cursor-pointer" style={{ color: 'var(--td)', border: '1px dashed var(--glass-b)' }} onClick={() => setIsCreatingCollection(true)}>+ New</button>
            )}
          </div>

          {/* Context menu */}
          {contextMenu && (
            <div className="fixed z-50 rounded-lg py-1 shadow-lg" style={{ left: contextMenu.x, top: contextMenu.y, background: 'var(--surface-menu)', border: '1px solid var(--glass-b)', minWidth: '140px' }}>
              {renamingCollectionId === contextMenu.id ? (
                <div className="px-3 py-2 flex items-center gap-1.5">
                  <input autoFocus className="text-xs outline-none flex-1" style={{ background: 'transparent', color: 'var(--text)' }} value={renameValue} onChange={(e) => setRenameValue(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void handleRenameCollection(contextMenu.id); if (e.key === 'Escape') { setRenamingCollectionId(null); setContextMenu(null) } }} />
                </div>
              ) : (
                <>
                  <button className="w-full text-left px-4 py-2 text-xs cursor-pointer hover:opacity-80" style={{ color: 'var(--text)' }} onClick={(e) => { e.stopPropagation(); const coll = collections.find((c) => c.id === contextMenu.id); setRenameValue(coll?.name ?? ''); setRenamingCollectionId(contextMenu.id) }}>Rename</button>
                  <button className="w-full text-left px-4 py-2 text-xs cursor-pointer hover:opacity-80" style={{ color: 'var(--src-error)' }} onClick={(e) => { e.stopPropagation(); void handleDeleteCollection(contextMenu.id) }}>Delete collection</button>
                </>
              )}
            </div>
          )}

          {filteredSources.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center" style={{ borderColor: 'var(--glass-b)' }}>
              <p className="text-sm" style={{ color: 'var(--td)' }}>
                {sources.length === 0 ? 'No sources yet. Add one to get started.' : 'No sources in this collection.'}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {filteredSources.map((s) => (
                <SourceCard
                  key={s.id}
                  source={s}
                  onProcess={handleProcess}
                  onReview={handleReview}
                  onExport={handleExport}
                  onDelete={handleDelete}
                  onRename={handleRename}
                  onReprocess={handleReprocessClick}
                  isProcessingLocal={processingIds.has(s.id)}
                  collections={collections}
                  onAssignCollection={handleAssignCollection}
                />
              ))}
            </div>
          )}
        </section>
      </main>
      {showTrackModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)' }}
        >
          <div
            className="rounded-2xl p-6 max-w-md w-full flex flex-col gap-5"
            style={{
              background: 'var(--surface-menu)',
              border: '1px solid var(--glass-b)',
              boxShadow: 'var(--sh)',
            }}
          >
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
              Choose tracks
            </h3>

            {subtitleTracks.length > 0 && (
              <div className="flex flex-col gap-2">
                <div className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--td)' }}>
                  Subtitle track
                </div>
                {subtitleTracks.map((track) => {
                  const isSelected = selectedSubtitleIndex === track.index
                  return (
                    <button
                      key={track.index}
                      onClick={() => setSelectedSubtitleIndex(track.index)}
                      className="glass-pill text-left cursor-pointer"
                      style={{
                        background: isSelected ? 'var(--abg)' : undefined,
                        border: isSelected ? '1px solid var(--accent)' : undefined,
                        color: 'var(--text)',
                      }}
                    >
                      <div className="text-sm font-medium">
                        {track.title ?? track.language ?? `Track ${track.index}`}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--tm)' }}>
                        {track.language ?? '—'} · {track.codec}
                      </div>
                    </button>
                  )
                })}
              </div>
            )}

            {audioTracks.length > 0 && (
              <div className="flex flex-col gap-2">
                <div className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--td)' }}>
                  Audio track
                </div>
                {audioTracks.map((track) => {
                  const isSelected = selectedAudioIndex === track.index
                  return (
                    <button
                      key={track.index}
                      onClick={() => setSelectedAudioIndex(track.index)}
                      className="glass-pill text-left cursor-pointer"
                      style={{
                        background: isSelected ? 'var(--abg)' : undefined,
                        border: isSelected ? '1px solid var(--accent)' : undefined,
                        color: 'var(--text)',
                      }}
                    >
                      <div className="text-sm font-medium">
                        {track.title ?? track.language ?? `Track ${track.index}`}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--tm)' }}>
                        {track.language ?? '—'} · {track.codec}
                        {track.channels != null && ` · ${track.channels}ch`}
                      </div>
                    </button>
                  )
                })}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-1">
              <button
                onClick={handleCancelTrackSelection}
                className="glass-pill text-xs cursor-pointer" style={{ color: 'var(--td)', padding: '4px 10px' }}
              >
                Cancel
              </button>
              <button
                onClick={() => void handleConfirmTracks()}
                className="glass-pill glass-pill-prominent text-xs font-medium text-white cursor-pointer"
                style={{ background: 'var(--accent)', color: '#fff' }}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
      {reprocessSourceId != null && (
        <ReprocessModal
          sourceId={reprocessSourceId}
          onClose={() => setReprocessSourceId(null)}
          onReprocess={handleReprocessConfirm}
          onOpenExport={(id) => { setReprocessSourceId(null); navigate(`/sources/${id}/export`) }}
        />
      )}
      {toast && <Toast key={toast.key} text={toast.text} onDone={() => setToast(null)} />}
    </div>
  )
}

function Toast({ text, onDone }: { text: string; onDone: () => void }): JSX.Element {
  useEffect(() => {
    const timer = setTimeout(onDone, 3500)
    return () => clearTimeout(timer)
  }, [onDone])

  return (
    <div
      className="fixed bottom-5 right-5 rounded-xl px-4 py-3 text-xs font-medium shadow-lg animate-fade-in-out z-50"
      style={{
        background: 'rgba(251,191,36,.12)',
        border: '1px solid rgba(251,191,36,.3)',
        color: '#fbbf24',
        backdropFilter: 'blur(12px)',
      }}
    >
      ⚠ {text}
    </div>
  )
}
