import { AlertTriangle, CheckCircle2, Loader2, Pencil, Sparkles, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CandidateStatus, StoredCandidate } from '@/api/types'

interface CandidateCardProps {
  candidate: StoredCandidate
  isHovered: boolean
  isRated: boolean
  onHoverEnter: (id: number) => void
  onHoverLeave: () => void
  onMark: (id: number, status: CandidateStatus) => Promise<void>
  onEditFragment?: (id: number) => void
  onCancelEditFragment?: () => void
  isEditingFragment?: boolean
  onGenerateMeaning?: (id: number) => void
  isGenerating?: boolean
}

const CEFR_COLOR: Record<string, string> = {
  B2: 'bg-amber-900/50 text-amber-400 border-amber-800',
  C1: 'bg-orange-900/50 text-orange-400 border-orange-800',
  C2: 'bg-rose-900/50 text-rose-400 border-rose-800',
}

const POS_LABEL: Record<string, string> = {
  NOUN: 'noun', VERB: 'verb', ADJ: 'adj', ADV: 'adv',
  PROPN: 'prop', NUM: 'num', PRON: 'pron', DET: 'det',
}

function freqLabel(zipf: number): string {
  if (zipf >= 4.5) return 'Common'
  if (zipf >= 3.0) return 'Uncommon'
  return 'Rare'
}

const STATUS_BORDER: Partial<Record<CandidateStatus, string>> = {
  learn: 'border-l-2 border-l-emerald-500/50',
  known: 'border-l-2 border-l-sky-500/50',
  skip:  'border-l-2 border-l-slate-500/40',
}

// Явный фон по статусу — нужен потому что backdrop-filter внутри overflow-контейнера
// размывает тёмный фон контейнера (а не fixed body gradient), делая карточки чёрными
const STATUS_BG: Partial<Record<CandidateStatus, string>> = {
  learn: 'rgba(16,185,129,0.09)',
  known: 'rgba(14,165,233,0.09)',
  skip:  'rgba(148,163,184,0.07)',
}

const MARK_BUTTONS: { status: CandidateStatus; label: string; cls: string; activeCls: string }[] = [
  {
    status: 'learn',
    label: 'Learn',
    cls: 'border-slate-700 text-slate-400 hover:border-emerald-700 hover:text-emerald-400',
    activeCls: 'border-emerald-600 bg-emerald-900/40 text-emerald-400',
  },
  {
    status: 'known',
    label: 'Know',
    cls: 'border-slate-700 text-slate-400 hover:border-sky-700 hover:text-sky-400',
    activeCls: 'border-sky-600 bg-sky-900/40 text-sky-400',
  },
  {
    status: 'skip',
    label: 'Skip',
    cls: 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-300',
    activeCls: 'border-slate-600 bg-slate-800/60 text-slate-300',
  },
]

export function CandidateCard({
  candidate,
  isHovered,
  isRated,
  onHoverEnter,
  onHoverLeave,
  onMark,
  onEditFragment,
  onCancelEditFragment,
  isEditingFragment,
  onGenerateMeaning,
  isGenerating,
}: CandidateCardProps) {
  const cefrCls = CEFR_COLOR[candidate.cefr_level ?? ''] ?? 'bg-slate-800 text-slate-400 border-slate-700'

  const handleMark = async (status: CandidateStatus) => {
    // Toggle: clicking active status → reset to pending
    const next: CandidateStatus = candidate.status === status ? 'pending' : status
    await onMark(candidate.id, next)
  }

  return (
    <div
      data-candidate-id={candidate.id}
      onMouseEnter={() => onHoverEnter(candidate.id)}
      onMouseLeave={onHoverLeave}
      className={cn(
        'glass-card rounded-xl p-4 flex flex-col gap-3',
        isRated && 'card-slide-in',
        isRated && STATUS_BORDER[candidate.status],
      )}
      style={{
        ...(isRated && {
          background: STATUS_BG[candidate.status] ?? 'rgba(148,163,184,0.07)',
          backdropFilter: 'none',
          WebkitBackdropFilter: 'none',
        }),
        ...(isEditingFragment
          ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 1px var(--accent)' }
          : isHovered && { borderColor: 'var(--accent)' }),
      }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base font-semibold" style={{ color: 'var(--text)' }}>{candidate.lemma}</span>
        {candidate.ipa && (
          <span className="text-xs font-mono" style={{ color: 'var(--td)' }}>{candidate.ipa}</span>
        )}
        <span className="rounded px-1.5 py-0.5 text-xs" style={{ color: 'var(--td)', background: 'var(--glass)', border: '1px solid var(--glass-b)' }}>
          {POS_LABEL[candidate.pos] ?? candidate.pos.toLowerCase()}
        </span>
        {candidate.is_phrasal_verb ? (
          <span className="rounded border px-1.5 py-0.5 text-xs font-medium bg-violet-900/40 text-violet-400 border-violet-800">
            phrasal
          </span>
        ) : candidate.cefr_level && (
          <span className={cn('rounded border px-1.5 py-0.5 text-xs font-medium', cefrCls)}>
            {candidate.cefr_level}
          </span>
        )}
        <span className="ml-auto text-xs" style={{ color: 'var(--td)' }}>{freqLabel(candidate.zipf_frequency)}</span>
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-start gap-1">
          <p className="flex-1 text-xs italic leading-relaxed" style={{ color: 'var(--tm)' }}>
            "{candidate.context_fragment}"
          </p>
          {isEditingFragment ? (
            <button
              onClick={onCancelEditFragment}
              aria-label="Cancel editing context fragment"
              className="shrink-0 mt-0.5 cursor-pointer transition-opacity hover:opacity-100 rounded"
              style={{ opacity: 0.8, color: 'var(--accent)' }}
            >
              <X size={12} />
            </button>
          ) : onEditFragment && (
            <button
              onClick={() => onEditFragment(candidate.id)}
              aria-label="Edit context fragment"
              className="shrink-0 mt-0.5 cursor-pointer transition-opacity hover:opacity-80"
              style={{ opacity: isHovered ? 0.5 : 0.15 }}
            >
              <Pencil size={11} style={{ color: 'var(--tm)' }} />
            </button>
          )}
        </div>
        {isEditingFragment && (
          <p className="text-xs" style={{ color: 'var(--accent)', opacity: 0.8 }}>
            Select new boundary in text →
          </p>
        )}
      </div>

      {candidate.meaning && (
        <p className="text-xs leading-relaxed" style={{ color: 'var(--tm)' }}>
          {candidate.meaning}
        </p>
      )}

      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-xs">
          {candidate.fragment_purity === 'clean' ? (
            <>
              <CheckCircle2 size={11} style={{ color: 'rgba(16,185,129,.8)' }} />
              <span style={{ color: 'rgba(16,185,129,.8)' }}>clean</span>
            </>
          ) : (
            <>
              <AlertTriangle size={11} style={{ color: 'rgba(245,158,11,.8)' }} />
              <span style={{ color: 'rgba(245,158,11,.8)' }}>noisy</span>
            </>
          )}
          {candidate.occurrences > 1 && (
            <span style={{ color: 'var(--td)' }}>· ×{candidate.occurrences}</span>
          )}
        </span>
        <span className="flex items-center gap-1.5">
          {candidate.is_sweet_spot && (
            <span className="text-xs" style={{ color: 'var(--accent)' }}>sweet spot</span>
          )}
          {onGenerateMeaning && (
            <button
              onClick={() => onGenerateMeaning(candidate.id)}
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
          )}
        </span>
      </div>

      <div className="flex gap-1.5">
        {MARK_BUTTONS.map(({ status, label, cls, activeCls }) => (
          <button
            key={status}
            onClick={() => void handleMark(status)}
            className={cn(
              'flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors',
              candidate.status === status ? activeCls : cls,
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
