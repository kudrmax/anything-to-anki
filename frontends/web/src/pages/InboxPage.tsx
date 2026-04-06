import { useCallback, useEffect, useRef, useState } from 'react'
import type { JSX } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Link, File, Upload, Loader2, Plus, RefreshCw } from 'lucide-react'
import { api } from '@/api/client'
import type { SourceSummary, SourceType, Stats } from '@/api/types'
import { SourceCard } from '@/components/SourceCard'
import { useSourcePolling } from '@/hooks/useSourcePolling'

function detectedFileType(files: File[]): string {
  const exts = files.map((f) => f.name.split('.').pop()?.toLowerCase() ?? '')
  if (exts.includes('epub')) return 'Book · epub'
  if (exts.some((e) => ['mp4', 'mkv', 'avi', 'mov'].includes(e)))
    return exts.includes('srt')
      ? 'Video + subtitles'
      : 'Video · ' + exts.find((e) => ['mp4', 'mkv', 'avi', 'mov'].includes(e))
  if (exts.includes('srt')) return 'Subtitles · srt'
  if (exts.includes('html')) return 'Article · html'
  return 'Text · ' + (exts[0] ?? 'txt')
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
  const [files, setFiles] = useState<File[]>([])
  const [adding, setAdding] = useState(false)
  const [processingAll, setProcessingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ text: string; key: number } | null>(null)
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set())
  const processingIdsRef = useRef(processingIds)
  processingIdsRef.current = processingIds
  const [cefrLevel, setCefrLevel] = useState('B2')

  const loadSources = useCallback(async () => {
    try {
      const [list, s] = await Promise.all([api.listSources(), api.getStats()])
      setSources(list)
      setStats(s)
    } catch {
      // ignore background reload errors
    }
  }, [])

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

    if (activeTab === 'url' || activeTab === 'file') {
      setToast({ text: 'This feature is not implemented yet', key: Date.now() })
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
        created_at: new Date().toISOString(),
        candidate_count: 0,
        learn_count: 0,
        processing_stage: null,
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

  const handleGlobalDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    if (activeTab !== 'file') setActiveTab('file')
  }

  const handleGlobalDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setActiveTab('file')
    setFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)])
  }

  const pendingCount = sources.filter((s) => s.status === 'new' || s.status === 'error').length
  const isSidebar = import.meta.env.VITE_LAYOUT === 'sidebar'

  const urlDetectedType =
    urlInput.includes('genius.com')
      ? 'Lyrics · Genius'
      : urlInput.includes('youtube.com') || urlInput.includes('youtu.be')
        ? 'Video · YouTube'
        : 'Article · web'

  return (
    <div className="flex-1 overflow-y-auto">
      <main className={
        isSidebar
          ? 'max-w-2xl mx-auto px-6 py-6 flex flex-col gap-6'
          : 'mx-auto max-w-6xl px-4 py-8 grid grid-cols-1 gap-8 lg:grid-cols-[400px_1fr]'
      }>
        {/* ── LEFT COLUMN: FORM ── */}
        <section
          className="flex flex-col gap-4"
          onDragOver={handleGlobalDragOver}
          onDrop={handleGlobalDrop}
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
            <div
              className="flex p-[3px] rounded-[10px] w-fit"
              style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)' }}
            >
              {(['text', 'url', 'file'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className="flex items-center gap-1.5 px-3.5 py-[5px] rounded-[7px] text-xs font-medium transition-all cursor-pointer"
                  style={
                    activeTab === tab
                      ? { background: 'var(--accent)', color: '#fff', boxShadow: '0 2px 8px var(--ag)' }
                      : { background: 'transparent', color: 'var(--tm)' }
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
                    {(['text', 'lyrics', 'subtitles'] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setTextSourceType(t)}
                        className="px-3 py-1 rounded-full text-[11px] font-medium capitalize transition-all cursor-pointer"
                        style={
                          textSourceType === t
                            ? { background: 'var(--accent)', color: '#fff', border: '1px solid var(--accent)' }
                            : { background: 'var(--glass)', color: 'var(--tm)', border: '1px solid var(--glass-b)' }
                        }
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder={
                    textSourceType === 'lyrics'
                      ? 'Paste song lyrics here…'
                      : textSourceType === 'subtitles'
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
                        background: 'rgba(129,140,248,.15)',
                        border: '1px solid rgba(129,140,248,.3)',
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
                {files.length === 0 && (
                  <div
                    onClick={() => document.getElementById('anki-file-input')?.click()}
                    className="flex flex-col items-center gap-2 rounded-[10px] p-6 text-center cursor-pointer transition-all"
                    style={{ border: '1.5px dashed rgba(129,140,248,.35)', background: 'rgba(129,140,248,.04)' }}
                    onMouseEnter={(e) => {
                      const el = e.currentTarget as HTMLDivElement
                      el.style.borderColor = 'var(--accent)'
                      el.style.background = 'rgba(129,140,248,.08)'
                    }}
                    onMouseLeave={(e) => {
                      const el = e.currentTarget as HTMLDivElement
                      el.style.borderColor = 'rgba(129,140,248,.35)'
                      el.style.background = 'rgba(129,140,248,.04)'
                    }}
                  >
                    <Upload size={28} style={{ color: 'rgba(129,140,248,.6)' }} />
                    <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>Drop file here</div>
                    <div className="text-[11px]" style={{ color: 'var(--td)' }}>
                      .epub · .srt · .html · .txt · .mp4 · .mkv · any video
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); document.getElementById('anki-file-input')?.click() }}
                      className="mt-1 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer"
                      style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
                    >
                      Choose file
                    </button>
                  </div>
                )}
                <input
                  id="anki-file-input"
                  type="file"
                  multiple
                  accept=".epub,.srt,.html,.txt,.mp4,.mkv,.avi,.mov"
                  className="hidden"
                  onChange={(e) => {
                    setFiles((prev) => [...prev, ...Array.from(e.target.files ?? [])])
                    e.target.value = ''
                  }}
                />
                {files.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    {files.map((f, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2.5 rounded-lg px-3 py-2"
                        style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)' }}
                      >
                        <File size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium truncate" style={{ color: 'var(--text)' }}>{f.name}</div>
                          <div className="text-[10px]" style={{ color: 'var(--tm)' }}>
                            {f.name.split('.').pop()?.toUpperCase()}
                          </div>
                        </div>
                        <button
                          onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                          className="text-xs cursor-pointer transition-colors hover:text-rose-400"
                          style={{ color: 'var(--td)' }}
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => document.getElementById('anki-file-input')?.click()}
                      className="text-[11px] text-left transition-colors cursor-pointer hover:brightness-125"
                      style={{ color: 'var(--tm)' }}
                    >
                      + Add another file
                    </button>
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full"
                        style={{
                          background: 'rgba(129,140,248,.15)',
                          border: '1px solid rgba(129,140,248,.3)',
                          color: 'var(--accent)',
                        }}
                      >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--accent)' }} />
                        {detectedFileType(files)}
                      </span>
                      <span
                        className="text-[11px] underline underline-offset-2 cursor-pointer"
                        style={{ color: 'var(--tm)' }}
                      >
                        change
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-xs text-rose-400">{error}</p>}

            <button
              onClick={() => void handleAdd()}
              disabled={adding}
              className="flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 transition-all hover:brightness-110 hover:-translate-y-px cursor-pointer"
              style={{ background: 'var(--accent)', boxShadow: '0 4px 14px var(--ag)' }}
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
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
                style={{ border: '1px solid var(--glass-b)', color: 'var(--tm)', background: 'var(--glass)' }}
              >
                {processingAll
                  ? <Loader2 size={11} className="animate-spin" />
                  : <RefreshCw size={11} />
                }
                Process all ({pendingCount})
              </button>
            )}
          </div>

          {sources.length === 0 ? (
            <div className="rounded-xl border border-dashed p-8 text-center" style={{ borderColor: 'var(--glass-b)' }}>
              <p className="text-sm" style={{ color: 'var(--td)' }}>No sources yet. Add one to get started.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {sources.map((s) => (
                <SourceCard
                  key={s.id}
                  source={s}
                  onProcess={handleProcess}
                  onReview={handleReview}
                  onExport={handleExport}
                  onDelete={handleDelete}
                  onRename={handleRename}
                  isProcessingLocal={processingIds.has(s.id)}
                />
              ))}
            </div>
          )}
        </section>
      </main>
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
