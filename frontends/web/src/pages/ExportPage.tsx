import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
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

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-slate-500" />
      </div>
    )
  }

  const canSync = ankiStatus?.available === true && cards.length > 0 && !syncing

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      <header className="border-b border-slate-800 px-6 py-3 flex items-center justify-between gap-4">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
        >
          <ArrowLeft size={14} />
          Back
        </button>

        <h1 className="text-sm font-medium text-slate-300">Export to Anki</h1>

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
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
            Cards to export{cards.length > 0 && ` (${cards.length})`}
          </h2>
          {!ankiStatus?.available && (
            <p className="text-xs text-slate-500">Launch Anki with AnkiConnect to sync</p>
          )}
        </div>

        {cards.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-800 p-8 text-center">
            <p className="text-sm text-slate-600">No words marked for learning.</p>
            <p className="text-xs text-slate-700 mt-1">
              Go to the review page and mark words as "Learn".
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {cards.map((card) => (
              <CardPreviewItem key={card.candidate_id} card={card} />
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
            className="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors cursor-pointer"
          >
            {syncing && <Loader2 size={14} className="animate-spin" />}
            {syncing ? 'Syncing…' : 'Add to Anki'}
          </button>
        )}
      </main>
    </div>
  )
}

function CardPreviewItem({ card }: { card: CardPreview }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-100">{card.lemma}</span>
        {card.ipa && (
          <span className="text-xs text-slate-500 font-mono shrink-0">{card.ipa}</span>
        )}
      </div>
      <p
        className="text-sm text-slate-300 italic leading-relaxed [&_b]:not-italic [&_b]:font-semibold [&_b]:text-slate-100"
        dangerouslySetInnerHTML={{ __html: card.sentence }}
      />
      {card.meaning ? (
        <p className="text-xs text-slate-400">{card.meaning}</p>
      ) : (
        <p className="text-xs text-slate-600 italic">No definition available</p>
      )}
    </div>
  )
}
