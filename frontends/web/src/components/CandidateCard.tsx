import { cn } from '@/lib/utils'
import type { CandidateStatus, StoredCandidate } from '@/api/types'

interface CandidateCardProps {
  candidate: StoredCandidate
  isHovered: boolean
  onHoverEnter: (id: number) => void
  onHoverLeave: () => void
  onMark: (id: number, status: CandidateStatus) => Promise<void>
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
  onHoverEnter,
  onHoverLeave,
  onMark,
}: CandidateCardProps) {
  const cefrCls = CEFR_COLOR[candidate.cefr_level] ?? 'bg-slate-800 text-slate-400 border-slate-700'

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
        'rounded-lg border bg-slate-900 p-4 flex flex-col gap-3 transition-colors',
        isHovered ? 'border-indigo-600' : 'border-slate-800',
      )}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base font-semibold text-slate-100">{candidate.lemma}</span>
        <span className="rounded px-1.5 py-0.5 text-xs text-slate-500 bg-slate-800 border border-slate-700">
          {POS_LABEL[candidate.pos] ?? candidate.pos.toLowerCase()}
        </span>
        <span className={cn('rounded border px-1.5 py-0.5 text-xs font-medium', cefrCls)}>
          {candidate.cefr_level}
        </span>
        <span className="ml-auto text-xs text-slate-500">{freqLabel(candidate.zipf_frequency)}</span>
      </div>

      <p className="text-xs italic text-slate-400 leading-relaxed">"{candidate.context_fragment}"</p>

      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-600">
          {candidate.fragment_purity === 'clean' ? '✅ clean' : '⚠️ noisy'}
          {candidate.occurrences > 1 && ` · ×${candidate.occurrences}`}
        </span>
        {candidate.is_sweet_spot && (
          <span className="text-xs text-indigo-400">sweet spot</span>
        )}
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
