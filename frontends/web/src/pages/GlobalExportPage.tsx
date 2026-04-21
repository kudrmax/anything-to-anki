import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, Sparkles } from 'lucide-react'
import { api } from '@/api/client'
import type { ExportSection, SyncResult } from '@/api/types'
import { useToolbarSlots } from '@/lib/useToolbarSlot'
import { useAnkiStatus } from '@/hooks/useAnkiStatus'
import { CardList } from '@/components/CardList'

export function GlobalExportPage() {
  const ankiStatus = useAnkiStatus()
  const [sections, setSections] = useState<ExportSection[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<SyncResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set())
  const [generatingAll, setGeneratingAll] = useState(false)
  const [toast, setToast] = useState<{ text: string; key: number } | null>(null)

  const totalCards = sections.reduce((sum, s) => sum + s.cards.length, 0)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.getExportCards()
        setSections(data.sections)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  const handleSync = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      const res = await api.syncToAnki()
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }, [])

  const handleGenerate = useCallback(async (candidateId: number) => {
    setGeneratingIds((prev) => new Set(prev).add(candidateId))
    try {
      const res = await api.generateMeaning(candidateId)
      setSections((prev) =>
        prev.map((section) => ({
          ...section,
          cards: section.cards.map((c) =>
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
        })),
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
      for (const section of sections) {
        await api.enqueueMeaningGeneration(section.source_id)
      }
      const updated = await api.getExportCards()
      setSections(updated.sections)
      setToast({ text: 'Generation started in background', key: Date.now() })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGeneratingAll(false)
    }
  }, [sections])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--tm)' }} />
      </div>
    )
  }

  const canSync = ankiStatus?.available === true && totalCards > 0 && !syncing
  const canGenerateAll = totalCards > 0 && !generatingAll && generatingIds.size === 0

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
          <div>
            <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--tm)' }}>
              Cards to export{totalCards > 0 && ` (${totalCards})`}
            </h2>
            {sections.length > 0 && (
              <p className="text-xs mt-0.5" style={{ color: 'var(--td)' }}>
                from {sections.length} source{sections.length !== 1 && 's'}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {!ankiStatus?.available && (
              <p className="text-xs" style={{ color: 'var(--td)' }}>Launch Anki with AnkiConnect to sync</p>
            )}
            {totalCards > 0 && (
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

        {totalCards === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center" style={{ borderColor: 'var(--glass-b)' }}>
            <p className="text-sm" style={{ color: 'var(--td)' }}>No words marked for learning.</p>
            <p className="text-xs mt-1" style={{ color: 'var(--td)', opacity: 0.7 }}>
              Go to the review page and mark words as "Learn".
            </p>
          </div>
        ) : (
          sections.map((section) => (
            <div key={section.source_id} className="flex flex-col gap-3">
              <h3 className="text-xs font-medium uppercase tracking-wider flex items-center gap-2" style={{ color: 'var(--td)' }}>
                <span>{section.source_title}</span>
                <span className="glass-pill" style={{ fontSize: '10px', padding: '2px 8px' }}>
                  {section.cards.length}
                </span>
              </h3>
              <CardList
                cards={section.cards}
                generatingIds={generatingIds}
                onGenerate={(id) => void handleGenerate(id)}
              />
            </div>
          ))
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

        {totalCards > 0 && (
          <button
            onClick={handleSync}
            disabled={!canSync}
            className="glass-pill glass-pill-prominent disabled:opacity-50 cursor-pointer"
            style={{ gap: '6px' }}
          >
            {syncing && <Loader2 size={14} className="animate-spin" />}
            {syncing ? 'Syncing…' : `Add to Anki · ${totalCards} cards`}
          </button>
        )}
      </main>

      {toast && <Toast key={toast.key} text={toast.text} onDone={() => setToast(null)} />}
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
