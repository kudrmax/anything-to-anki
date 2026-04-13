import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { createPortal } from 'react-dom'
import { BookOpen, Languages, Loader2, Sparkles, Volume2 } from 'lucide-react'
import { api } from '@/api/client'
import type { CardPreview, SyncResult } from '@/api/types'
import { useToolbarSlots } from '@/lib/useToolbarSlot'
import { useAnkiStatus } from '@/hooks/useAnkiStatus'
import { ToolbarButton } from '@/components/CandidateCardV2'
import { MediaThumbnail } from '@/components/MediaThumbnail'

export function ExportPage() {
  const { id } = useParams<{ id: string }>()
  const sourceId = Number(id)

  const ankiStatus = useAnkiStatus()
  const [cards, setCards] = useState<CardPreview[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<SyncResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [generatingAll, setGeneratingAll] = useState(false)
  const [toast, setToast] = useState<{ text: string; key: number } | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const cardList = await api.getSourceCards(sourceId)
        setCards(cardList)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [sourceId])

  const handleSync = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      const res = await api.syncToAnki(sourceId)
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }, [sourceId])

  const handleGenerate = useCallback(async (candidateId: number) => {
    setGeneratingIds((prev) => new Set(prev).add(candidateId))
    try {
      const res = await api.generateMeaning(candidateId)
      setCards((prev) =>
        prev.map((c) =>
          c.candidate_id === candidateId
            ? {
                ...c,
                meaning: res.meaning,
                translation: res.translation,
                synonyms: res.synonyms,
                examples: res.examples,
                ipa: res.ipa,
              }
            : c,
        ),
      )
      setToast({ text: `Tokens used: ${res.tokens_used}`, key: Date.now() })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGeneratingIds((prev) => {
        const next = new Set(prev)
        next.delete(candidateId)
        return next
      })
    }
  }, [])

  const handleGenerateAll = useCallback(async () => {
    setGeneratingAll(true)
    setError(null)
    try {
      await api.enqueueMeaningGeneration(sourceId)
      const updated = await api.getSourceCards(sourceId)
      setCards(updated)
      setToast({ text: 'Generation started in background', key: Date.now() })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGeneratingAll(false)
    }
  }, [sourceId])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  const canSync = ankiStatus?.available === true && cards.length > 0 && !syncing
  const canGenerateAll = cards.length > 0 && !generatingAll && generatingIds.size === 0

  const toolbarSlots = useToolbarSlots()

  return (
    <div className="flex-1 overflow-y-auto">
      {toolbarSlots.right.current && createPortal(
        <>
          <div className="glass-pill" style={{ gap: '4px' }}>
            {ankiStatus ? (
              ankiStatus.available ? (
                <>
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: 'var(--status-learn)' }} />
                  <span style={{ color: 'var(--status-learn)' }}>Anki connected</span>
                </>
              ) : (
                <>
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: 'var(--error)' }} />
                  <span style={{ color: 'var(--td)' }}>Anki unavailable</span>
                </>
              )
            ) : (
              <span style={{ color: 'var(--td)' }}>Checking…</span>
            )}
          </div>
        </>,
        toolbarSlots.right.current,
      )}

      <main className="mx-auto max-w-2xl px-4 py-8 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
            Cards to export{cards.length > 0 && ` (${cards.length})`}
          </h2>
          <div className="flex items-center gap-3">
            {!ankiStatus?.available && (
              <p className="text-xs" style={{ color: 'var(--td)' }}>Launch Anki with AnkiConnect to sync</p>
            )}
            {cards.length > 0 && (
              <button
                onClick={handleGenerateAll}
                disabled={!canGenerateAll}
                className="glass-pill disabled:opacity-50 cursor-pointer"
                style={{ gap: '6px', color: 'var(--tm)' }}
              >
                {generatingAll ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Sparkles size={12} />
                )}
                {generatingAll ? 'Generating…' : 'Generate All'}
              </button>
            )}
          </div>
        </div>

        {cards.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center" style={{ borderColor: 'var(--glass-b)' }}>
            <p className="text-sm" style={{ color: 'var(--td)' }}>No words marked for learning.</p>
            <p className="text-xs mt-1" style={{ color: 'var(--td)', opacity: 0.7 }}>
              Go to the review page and mark words as "Learn".
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {cards.map((card) => (
              <CardPreviewItem
                key={card.candidate_id}
                card={card}
                isGenerating={generatingIds.has(card.candidate_id)}
                onGenerate={() => void handleGenerate(card.candidate_id)}
              />
            ))}
          </div>
        )}

        {result && (
          <div className="rounded-lg border border-emerald-800 bg-emerald-900/20 px-4 py-3 text-sm flex flex-col gap-1.5">
            <div className="flex flex-wrap gap-x-1 items-center">
              <span className="text-emerald-300 font-medium">Added: {result.added}</span>
              <span className="text-slate-600">·</span>
              <span className="text-slate-400">Skipped: {result.skipped}</span>
              {result.errors > 0 && (
                <>
                  <span className="text-slate-600">·</span>
                  <span className="text-rose-400">Errors: {result.errors}</span>
                </>
              )}
            </div>
            {result.skipped_lemmas.length > 0 && (
              <p className="text-xs text-slate-500">
                Already in Anki: {result.skipped_lemmas.join(', ')}
              </p>
            )}
            {result.error_lemmas.length > 0 && (
              <p className="text-xs text-rose-400">
                Failed: {result.error_lemmas.join(', ')}
              </p>
            )}
          </div>
        )}

        {error && <p className="text-xs text-rose-400">{error}</p>}

        {cards.length > 0 && (
          <button
            onClick={handleSync}
            disabled={!canSync}
            className="glass-pill glass-pill-prominent disabled:opacity-50 cursor-pointer"
            style={{ gap: '6px' }}
          >
            {syncing && <Loader2 size={14} className="animate-spin" />}
            {syncing ? 'Syncing…' : 'Add to Anki'}
          </button>
        )}
      </main>

      {toast && <Toast key={toast.key} text={toast.text} onDone={() => setToast(null)} />}
    </div>
  )
}

interface CardPreviewItemProps {
  card: CardPreview
  isGenerating: boolean
  onGenerate: () => void
}

function CardPreviewItem({ card, isGenerating, onGenerate }: CardPreviewItemProps) {
  const [audioPlaying, setAudioPlaying] = useState(false)

  const handlePlayAudio = useCallback(() => {
    if (!card.audio_url) return
    const audio = new Audio(card.audio_url)
    setAudioPlaying(true)
    audio.onended = () => setAudioPlaying(false)
    audio.onerror = () => setAudioPlaying(false)
    void audio.play()
  }, [card.audio_url])

  return (
    <div className="glass-card rounded-xl p-4 flex flex-col gap-2" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: '12px', right: '12px', zIndex: 1 }}>
        <ToolbarButton
          onClick={onGenerate}
          disabled={isGenerating}
          title="Generate meaning with AI"
          ariaLabel="Generate meaning with AI"
        >
          {isGenerating ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
        </ToolbarButton>
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        {(card.screenshot_url || card.audio_url) && (
          <div style={{ flexShrink: 0, width: '160px' }}>
            <MediaThumbnail
              screenshotUrl={card.screenshot_url}
              audioUrl={card.audio_url}
              isAudioPlaying={audioPlaying}
              onPlayAudio={handlePlayAudio}
              alt={`Screenshot for ${card.lemma}`}
            />
          </div>
        )}

        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <p
            className="text-sm leading-relaxed"
            style={{ color: 'var(--tm)' }}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: card.sentence }}
          />

          {card.meaning ? (
            <p
              className="text-xs"
              style={{ color: 'var(--tm)', marginTop: '4px' }}
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: card.meaning }}
            />
          ) : (
            <p className="text-xs italic" style={{ color: 'var(--td)' }}>No definition available</p>
          )}

          {card.translation && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', color: 'var(--text-muted-light)', lineHeight: 1.5 }}>
              <Languages size={14} style={{ marginTop: '2px', flexShrink: 0, color: 'var(--tm)' }} />
              <span style={{ color: 'var(--tm)' }}>{card.translation}</span>
            </div>
          )}

          {card.synonyms && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', color: 'var(--text-muted-light)', lineHeight: 1.5 }}>
              <BookOpen size={14} style={{ marginTop: '2px', flexShrink: 0, color: 'var(--tm)' }} />
              <span style={{ color: 'var(--tm)' }}>{card.synonyms}</span>
            </div>
          )}

          {card.ipa && (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', color: 'var(--text-muted-light)', lineHeight: 1.5 }}>
              <Volume2 size={13} style={{ flexShrink: 0, color: 'var(--tm)' }} />
              <span style={{ fontFamily: 'monospace', fontSize: '13px', color: 'var(--tm)' }}>{card.ipa}</span>
            </div>
          )}

          {card.examples && (
            <div
              style={{
                marginTop: '6px',
                padding: '8px 12px',
                background: 'var(--glass)',
                borderRadius: '8px',
                border: '1px solid var(--glass-b)',
              }}
            >
              {card.examples
                .split(/\n+/)
                .filter((l) => l.trim().length > 0)
                .map((line, i) => (
                  <p
                    key={i}
                    style={{
                      margin: i === 0 ? 0 : '4px 0 0',
                      fontSize: '12px',
                      lineHeight: 1.5,
                      color: 'var(--tm)',
                    }}
                  >
                    {line}
                  </p>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Toast({ text, onDone }: { text: string; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 3000)
    return () => clearTimeout(timer)
  }, [onDone])

  return (
    <div
      className="fixed bottom-4 right-4 rounded-lg px-4 py-2.5 text-xs font-medium shadow-lg animate-fade-in-out"
      style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
    >
      {text}
    </div>
  )
}
