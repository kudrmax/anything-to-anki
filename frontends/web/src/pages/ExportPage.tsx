import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Sparkles } from 'lucide-react'
import { api } from '@/api/client'
import type { AnkiStatus, CardPreview, SyncResult } from '@/api/types'

export function ExportPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const sourceId = Number(id)

  const [ankiStatus, setAnkiStatus] = useState<AnkiStatus | null>(null)
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
        const [status, cardList] = await Promise.all([
          api.getAnkiStatus(),
          api.getSourceCards(sourceId),
        ])
        setAnkiStatus(status)
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
        prev.map((c) => (c.candidate_id === candidateId ? { ...c, meaning: res.meaning } : c)),
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
      await api.startGeneration(sourceId)
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

  return (
    <div className="flex-1 overflow-y-auto">
      <header
        className="px-6 py-3 flex items-center justify-between gap-4"
        style={{ borderBottom: '1px solid var(--glass-b)' }}
      >
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm transition-opacity hover:opacity-100 cursor-pointer"
          style={{ color: 'var(--tm)', opacity: 0.8 }}
        >
          <ArrowLeft size={14} />
          Back
        </button>

        <h1 className="text-sm font-medium" style={{ color: 'var(--text)' }}>Export to Anki</h1>

        <div className="flex items-center gap-2 text-xs">
          {ankiStatus ? (
            ankiStatus.available ? (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                <span className="text-emerald-400">Anki connected</span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-rose-500" />
                <span className="text-slate-500">Anki unavailable</span>
              </>
            )
          ) : (
            <span className="text-slate-600">Checking…</span>
          )}
        </div>
      </header>

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
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
                style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
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
            className="flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
            style={{ background: 'var(--accent)' }}
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
  return (
    <div className="glass-card rounded-xl p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold" style={{ color: 'var(--text)' }}>{card.lemma}</span>
        <div className="flex items-center gap-2 shrink-0">
          {card.ipa && (
            <span className="text-xs font-mono" style={{ color: 'var(--td)' }}>{card.ipa}</span>
          )}
          <button
            onClick={onGenerate}
            disabled={isGenerating}
            title="Generate meaning with AI"
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-md disabled:opacity-50 transition-all hover:brightness-110 cursor-pointer"
            style={{ background: 'var(--glass)', border: '1px solid var(--glass-b)', color: 'var(--tm)' }}
          >
            {isGenerating ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <Sparkles size={11} />
            )}
          </button>
        </div>
      </div>
      <p
        className="text-sm italic leading-relaxed"
        style={{ color: 'var(--tm)' }}
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: card.sentence }}
      />
      {card.meaning ? (
        <p
          className="text-xs"
          style={{ color: 'var(--tm)' }}
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: card.meaning }}
        />
      ) : (
        <p className="text-xs italic" style={{ color: 'var(--td)' }}>No definition available</p>
      )}
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
