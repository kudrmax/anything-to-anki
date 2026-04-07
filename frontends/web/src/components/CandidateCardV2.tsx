import { useEffect, useRef, useState } from 'react'
import { Info, Loader2, Pencil, RefreshCw, Sparkles, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CandidateStatus, StoredCandidate } from '@/api/types'

interface CandidateCardV2Props {
  candidate: StoredCandidate
  sourceId: number
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
  screenshotUrl?: string | null
  audioUrl?: string | null
  onRegenerateMedia?: (id: number) => void
  isRegeneratingMedia?: boolean
  hasMediaTimecodes?: boolean
}

const CEFR_COLOR: Record<string, { bg: string; text: string; border: string }> = {
  B2: { bg: 'rgba(180,83,9,0.2)', text: '#fbbf24', border: 'rgba(180,83,9,0.3)' },
  C1: { bg: 'rgba(234,88,12,0.2)', text: '#fb923c', border: 'rgba(234,88,12,0.3)' },
  C2: { bg: 'rgba(225,29,72,0.2)', text: '#fb7185', border: 'rgba(225,29,72,0.3)' },
}

const CEFR_DEFAULT = { bg: 'rgba(148,163,184,0.15)', text: '#94a3b8', border: 'rgba(148,163,184,0.2)' }

const POS_LABEL: Record<string, string> = {
  NOUN: 'noun', VERB: 'verb', ADJ: 'adjective', ADV: 'adverb',
  PROPN: 'proper noun', NUM: 'numeral', PRON: 'pronoun', DET: 'determiner',
}

const STATUS_BORDER: Partial<Record<CandidateStatus, string>> = {
  learn: 'border-l-2 border-l-emerald-500/50',
  known: 'border-l-2 border-l-sky-500/50',
  skip:  'border-l-2 border-l-red-500/40',
}

const STATUS_BG: Partial<Record<CandidateStatus, string>> = {
  learn: 'rgba(16,185,129,0.09)',
  known: 'rgba(14,165,233,0.09)',
  skip:  'rgba(239,68,68,0.07)',
}

const MARK_BUTTONS: { status: CandidateStatus; label: string; bg: string; color: string; border: string; hoverBg: string }[] = [
  {
    status: 'learn',
    label: 'Learn',
    bg: 'rgba(52,211,153,0.2)',
    color: '#34d399',
    border: 'rgba(52,211,153,0.35)',
    hoverBg: 'rgba(52,211,153,0.3)',
  },
  {
    status: 'known',
    label: 'Know',
    bg: 'rgba(56,189,248,0.15)',
    color: '#38bdf8',
    border: 'rgba(56,189,248,0.3)',
    hoverBg: 'rgba(56,189,248,0.25)',
  },
  {
    status: 'skip',
    label: 'Skip',
    bg: 'rgba(239,68,68,0.15)',
    color: '#f87171',
    border: 'rgba(239,68,68,0.3)',
    hoverBg: 'rgba(239,68,68,0.25)',
  },
]

const MARK_ACTIVE: Record<string, { bg: string; color: string; border: string }> = {
  learn: { bg: 'rgba(16,185,129,0.35)', color: '#34d399', border: 'rgba(52,211,153,0.5)' },
  known: { bg: 'rgba(14,165,233,0.3)', color: '#38bdf8', border: 'rgba(56,189,248,0.5)' },
  skip:  { bg: 'rgba(239,68,68,0.3)', color: '#f87171', border: 'rgba(239,68,68,0.5)' },
}

function stripMarkdown(text: string): string {
  return text
    .replace(/\*{2}(.+?)\*{2}/gs, '$1')
    .replace(/_{2}(.+?)_{2}/gs, '$1')
    .replace(/\*(.+?)\*/gs, '$1')
    .replace(/_(.+?)_/gs, '$1')
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function buildHighlightPattern(lemma: string, surfaceForm: string | null): RegExp {
  const patterns: string[] = []
  if (surfaceForm) patterns.push(escapeRegex(surfaceForm))
  const words = lemma.split(' ')
  if (words.length === 1) {
    patterns.push(`\\b${escapeRegex(lemma)}\\w*`)
  } else {
    const rest = words.slice(1).map(escapeRegex).join('\\s+')
    patterns.push(`\\b${escapeRegex(words[0])}\\w*\\s+${rest}\\b`)
  }
  return new RegExp(`(${patterns.join('|')})`, 'gi')
}

function highlightWord(fragment: string, lemma: string, surfaceForm: string | null): React.ReactElement {
  const clean = stripMarkdown(fragment)
  const pattern = buildHighlightPattern(lemma, surfaceForm)
  const match = pattern.exec(clean)
  if (!match) {
    return <>{clean}</>
  }
  const before = clean.slice(0, match.index)
  const after = clean.slice(match.index + match[0].length)
  return (
    <>
      {before}
      <span style={{
        color: '#eef0ff',
        fontWeight: 700,
        fontSize: '22px',
        textDecoration: 'underline',
        textDecorationColor: '#818cf8',
        textUnderlineOffset: '4px',
      }}>
        {match[0]}
      </span>
      {after}
    </>
  )
}

function renderMeaning(text: string, lemma: string, surfaceForm: string | null): React.ReactElement {
  const clean = stripMarkdown(text)
  const pattern = buildHighlightPattern(lemma, surfaceForm)
  const parts: React.ReactNode[] = []
  let last = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(clean)) !== null) {
    if (match.index > last) parts.push(clean.slice(last, match.index))
    parts.push(
      <span key={match.index} style={{ fontWeight: 700, color: '#eef0ff' }}>
        {match[0]}
      </span>,
    )
    last = match.index + match[0].length
  }
  if (last < clean.length) parts.push(clean.slice(last))
  return <>{parts}</>
}

const TOOLBAR_BTN_CLS = [
  'w-7 h-7 flex items-center justify-center rounded-md cursor-pointer',
  'outline-none focus:outline-none focus-visible:outline-none',
  'border border-white/[0.08] bg-white/[0.04] text-slate-600',
  'hover:text-slate-400 hover:border-white/[0.15] hover:bg-white/[0.08]',
  'transition-colors',
].join(' ')

function ToolbarButton({ children, onClick, disabled, title, ariaLabel, className: extraCls }: {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  title?: string
  ariaLabel?: string
  className?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={ariaLabel}
      className={cn(TOOLBAR_BTN_CLS, disabled && 'opacity-50', extraCls)}
    >
      {children}
    </button>
  )
}

export function CandidateCardV2({
  candidate,
  sourceId,
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
  screenshotUrl,
  audioUrl,
  onRegenerateMedia,
  isRegeneratingMedia,
  hasMediaTimecodes,
}: CandidateCardV2Props) {
  const [showInfo, setShowInfo] = useState(false)
  const [isAudioPlaying, setIsAudioPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  const toggleAudio = (url: string) => {
    if (isAudioPlaying && audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      setIsAudioPlaying(false)
      return
    }
    const audio = new Audio(url)
    audioRef.current = audio
    audio.addEventListener('ended', () => setIsAudioPlaying(false))
    audio.addEventListener('error', () => setIsAudioPlaying(false))
    audio.play().then(() => setIsAudioPlaying(true)).catch(() => setIsAudioPlaying(false))
  }

  const handleMark = async (status: CandidateStatus) => {
    const next: CandidateStatus = candidate.status === status ? 'pending' : status
    await onMark(candidate.id, next)
  }

  const cefr = CEFR_COLOR[candidate.cefr_level ?? ''] ?? CEFR_DEFAULT

  return (
    <div
      data-candidate-id={candidate.id}
      onMouseEnter={() => onHoverEnter(candidate.id)}
      onMouseLeave={onHoverLeave}
      className={cn(
        'glass-card rounded-xl',
        isRated && 'card-slide-in',
        isRated && STATUS_BORDER[candidate.status],
      )}
      style={{
        position: 'relative',
        padding: '20px 20px 20px 24px',
        ...(isRated && {
          background: STATUS_BG[candidate.status] ?? 'rgba(148,163,184,0.07)',
          backdropFilter: 'none',
          WebkitBackdropFilter: 'none',
        }),
        ...(isEditingFragment
          ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 1px var(--accent)' }
          : isHovered ? { borderColor: 'var(--accent)' } : {}),
      }}
    >
      {/* Sweet spot gradient bar */}
      {candidate.is_sweet_spot && (
        <div style={{
          width: '3px',
          height: '100%',
          borderRadius: '12px 0 0 12px',
          background: 'linear-gradient(180deg, #818cf8, #67e8f9)',
          position: 'absolute',
          left: 0,
          top: 0,
        }} />
      )}

      {/* Right column: toolbar + CEFR */}
      <div style={{
        position: 'absolute',
        top: '20px',
        right: '20px',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        zIndex: 2,
      }}>
        {(candidate.is_phrasal_verb || candidate.cefr_level) && (
          candidate.is_phrasal_verb ? (
            <span className="rounded border px-1.5 py-0.5 text-xs font-medium bg-violet-900/40 text-violet-400 border-violet-800">
              phrasal
            </span>
          ) : (
            <span style={{
              fontSize: '10px',
              fontWeight: 600,
              background: cefr.bg,
              color: cefr.text,
              border: `1px solid ${cefr.border}`,
              borderRadius: '4px',
              padding: '1px 6px',
              whiteSpace: 'nowrap',
            }}>
              {candidate.cefr_level}
            </span>
          )
        )}
        {isEditingFragment ? (
          <ToolbarButton
            onClick={onCancelEditFragment}
            ariaLabel="Cancel editing context fragment"
            className="border-[var(--accent)] text-[var(--accent)]"
          >
            <X size={13} />
          </ToolbarButton>
        ) : onEditFragment && (
          <ToolbarButton
            onClick={() => onEditFragment(candidate.id)}
            ariaLabel="Edit context fragment"
            title="Edit context fragment"
          >
            <Pencil size={13} />
          </ToolbarButton>
        )}
        {onGenerateMeaning && (
          <ToolbarButton
            onClick={() => onGenerateMeaning(candidate.id)}
            disabled={isGenerating}
            ariaLabel="Generate meaning with AI"
            title="Generate meaning with AI"
          >
            {isGenerating ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          </ToolbarButton>
        )}
        {onRegenerateMedia && hasMediaTimecodes && (
          <ToolbarButton
            onClick={() => onRegenerateMedia(candidate.id)}
            disabled={isRegeneratingMedia}
            ariaLabel="Regenerate media for this candidate"
            title="Regenerate screenshot and audio (uses current fragment boundaries)"
          >
            {isRegeneratingMedia ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          </ToolbarButton>
        )}
        <div
          className="relative"
          onMouseEnter={() => setShowInfo(true)}
          onMouseLeave={() => setShowInfo(false)}
        >
          <ToolbarButton ariaLabel="Word info" title="Word info">
            <Info size={13} />
          </ToolbarButton>
          {showInfo && (
            <div style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: '6px',
              background: 'rgba(15,17,30,0.95)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: '8px',
              padding: '8px 12px',
              whiteSpace: 'nowrap',
              zIndex: 10,
              boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            }}>
              {candidate.meaning?.ipa && (
                <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#94a3b8' }}>
                  {candidate.meaning.ipa}
                </span>
              )}
              <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>
                · {POS_LABEL[candidate.pos] ?? candidate.pos.toLowerCase()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Horizontal split: media left, content right */}
      <div style={{ display: 'flex', gap: '14px', paddingRight: '120px' }}>
        {/* LEFT: Media column */}
        {(() => {
          // Derive URLs from candidate.media (preferred), fall back to mediaMap props
          // (mediaMap is built from /sources/{id}/cards which is LEARN-only).
          const candShot = candidate.media?.screenshot_path
            ? `/media/${sourceId}/${candidate.media.screenshot_path.split('/').pop()}`
            : null
          const candAudio = candidate.media?.audio_path
            ? `/media/${sourceId}/${candidate.media.audio_path.split('/').pop()}`
            : null
          const finalShot = candShot ?? screenshotUrl ?? null
          const finalAudio = candAudio ?? audioUrl ?? null
          const mediaStatus = candidate.media?.status
          const showMediaColumn = finalShot || finalAudio
            || mediaStatus === 'queued' || mediaStatus === 'running' || mediaStatus === 'failed'
          if (!showMediaColumn) return null
          return (
            <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '6px', width: '160px' }}>
              {finalShot ? (
                <img
                  src={finalShot}
                  alt="Scene screenshot"
                  width={160}
                  height={90}
                  style={{
                    objectFit: 'cover',
                    borderRadius: '8px',
                    border: '1px solid var(--glass-b)',
                    display: 'block',
                  }}
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                />
              ) : (
                <div style={{
                  width: '160px',
                  height: '90px',
                  borderRadius: '8px',
                  border: '1px dashed var(--glass-b)',
                  background: 'var(--glass)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  color: 'var(--td)',
                  gap: '6px',
                }}>
                  {mediaStatus === 'running' && (
                    <>
                      <Loader2 size={12} className="animate-spin" /> Generating
                    </>
                  )}
                  {mediaStatus === 'queued' && 'Queued'}
                  {mediaStatus === 'failed' && (
                    <span style={{ color: '#f87171' }} title={candidate.media?.error ?? undefined}>
                      Failed
                    </span>
                  )}
                </div>
              )}
              {finalAudio && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    toggleAudio(finalAudio)
                  }}
                  className="flex items-center justify-center gap-1.5 text-xs cursor-pointer"
                  style={{
                    width: '160px',
                    padding: '5px 0',
                    borderRadius: '6px',
                    border: '1px solid var(--glass-b)',
                    background: 'var(--glass)',
                    color: 'var(--accent)',
                  }}
                >
                  {isAudioPlaying ? '■ Stop audio' : '▶ Play audio'}
                </button>
              )}
            </div>
          )
        })()}

        {/* RIGHT: Text content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: '0 0 10px',
            fontSize: '17px',
            color: '#c4b5fd',
            lineHeight: 1.5,
          }}>
            &ldquo;{highlightWord(candidate.context_fragment, candidate.lemma, candidate.surface_form)}&rdquo;
          </p>

          {isEditingFragment && (
            <p style={{ margin: '0 0 10px', fontSize: '12px', color: 'var(--accent)', opacity: 0.8 }}>
              Select new boundary in text →
            </p>
          )}

          {candidate.meaning?.meaning ? (
            <p style={{
              margin: '0 0 14px',
              fontSize: '15px',
              lineHeight: 1.45,
              color: '#cbd5e1',
              whiteSpace: 'pre-line',
            }}>
              {renderMeaning(candidate.meaning.meaning, candidate.lemma, candidate.surface_form)}
            </p>
          ) : candidate.meaning?.status === 'running' ? (
            <p style={{ margin: '0 0 14px', fontSize: '13px', color: 'var(--td)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Loader2 size={13} className="animate-spin" /> Generating...
            </p>
          ) : candidate.meaning?.status === 'queued' ? (
            <p style={{ margin: '0 0 14px', fontSize: '13px', color: 'var(--td)' }}>Queued</p>
          ) : candidate.meaning?.status === 'failed' ? (
            <p style={{ margin: '0 0 14px', fontSize: '13px', color: '#f87171' }} title={candidate.meaning.error ?? undefined}>
              Failed to generate
            </p>
          ) : null}

          <div style={{ display: 'flex', gap: '10px' }}>
            {MARK_BUTTONS.map((btn) => {
              const isActive = candidate.status === btn.status
              const active = MARK_ACTIVE[btn.status]
              return (
                <button
                  key={btn.status}
                  onClick={() => void handleMark(btn.status)}
                  className="flex-1 rounded-lg cursor-pointer transition-colors"
                  style={{
                    border: `1px solid ${isActive ? active.border : btn.border}`,
                    borderRadius: '8px',
                    padding: '9px 0',
                    fontSize: '12px',
                    fontWeight: isActive ? 600 : 500,
                    background: isActive ? active.bg : btn.bg,
                    color: isActive ? active.color : btn.color,
                    textAlign: 'center',
                  }}
                >
                  {btn.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
