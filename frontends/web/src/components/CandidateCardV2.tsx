import { useRef, useState } from 'react'
import { BookOpen, ChevronDown, Film, Info, Languages, Loader2, Pencil, Play, Sparkles, Square, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/lib/ThemeProvider'
import LiquidGlass from 'liquid-glass-react'
import type { CandidateStatus, FollowUpAction, StoredCandidate } from '@/api/types'

const FOLLOW_UP_PRESETS: { action: FollowUpAction; label: string }[] = [
  { action: 'give_examples', label: 'Give examples' },
  { action: 'explain_detail', label: 'Explain in detail' },
  { action: 'explain_simpler', label: 'Explain simpler' },
  { action: 'how_to_say', label: 'How to say it' },
]

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
  onFollowUp?: (id: number, action: FollowUpAction, text?: string) => void
  screenshotUrl?: string | null
  audioUrl?: string | null
  onRegenerateMedia?: (id: number) => void
  isRegeneratingMedia?: boolean
  hasMediaTimecodes?: boolean
  // Audio playback is lifted to the parent so that:
  //  - only one audio plays at a time across cards
  //  - the parent can auto-play the next card's audio after a mark click
  isAudioPlaying: boolean
  onPlayAudio: (url: string) => void
  onStopAudio: () => void
}

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

const MARK_BUTTONS: { status: CandidateStatus; label: string; bg: string; color: string; border: string }[] = [
  { status: 'learn', label: 'Learn', bg: 'var(--status-learn-bg)', color: 'var(--status-learn)', border: 'var(--status-learn-border)' },
  { status: 'known', label: 'Know', bg: 'var(--status-know-bg)', color: 'var(--status-know)', border: 'var(--status-know-border)' },
  { status: 'skip', label: 'Skip', bg: 'var(--status-skip-bg)', color: 'var(--status-skip)', border: 'var(--status-skip-border)' },
]

const MARK_ACTIVE: Record<string, { bg: string; color: string; border: string }> = {
  learn: { bg: 'var(--status-learn-active-bg)', color: 'var(--status-learn)', border: 'var(--status-learn-active-border)' },
  known: { bg: 'var(--status-know-active-bg)', color: 'var(--status-know)', border: 'var(--status-know-active-border)' },
  skip: { bg: 'var(--status-skip-active-bg)', color: 'var(--status-skip)', border: 'var(--status-skip-active-border)' },
}

const CEFR_PILL_COLOR: Record<string, { bg: string; color: string }> = {
  B2: { bg: 'rgba(180,83,9,0.18)',  color: '#fbbf24' },
  C1: { bg: 'rgba(234,88,12,0.2)',  color: '#fb923c' },
  C2: { bg: 'rgba(225,29,72,0.2)',  color: '#fb7185' },
}
const CEFR_PILL_DEFAULT = { bg: 'rgba(148,163,184,0.15)', color: 'var(--tm)' }

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
        color: 'var(--text-primary)',
        fontWeight: 700,
        fontSize: '22px',
        textDecoration: 'underline',
        textDecorationColor: 'var(--accent)',
        textUnderlineOffset: '4px',
      }}>
        {match[0]}
      </span>
      {after}
    </>
  )
}

function renderMeaning(text: string, lemma: string, surfaceForm: string | null): React.ReactElement {
  const pattern = buildHighlightPattern(lemma, surfaceForm)
  const parts: React.ReactNode[] = []
  // Split by **bold** markers first
  const boldPattern = /\*{2}(.+?)\*{2}/g
  let idx = 0
  let boldMatch: RegExpExecArray | null

  const addTextWithHighlight = (segment: string, bold: boolean, keyPrefix: string) => {
    const p = new RegExp(pattern.source, pattern.flags)
    let last = 0
    let m: RegExpExecArray | null
    while ((m = p.exec(segment)) !== null) {
      if (m.index > last) {
        const t = segment.slice(last, m.index)
        parts.push(bold ? <b key={`${keyPrefix}-b-${last}`}>{t}</b> : t)
      }
      parts.push(
        <span key={`${keyPrefix}-h-${m.index}`} style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
          {m[0]}
        </span>,
      )
      last = m.index + m[0].length
    }
    if (last < segment.length) {
      const t = segment.slice(last)
      parts.push(bold ? <b key={`${keyPrefix}-b-${last}`}>{t}</b> : t)
    }
  }

  while ((boldMatch = boldPattern.exec(text)) !== null) {
    if (boldMatch.index > idx) {
      addTextWithHighlight(text.slice(idx, boldMatch.index), false, `t${idx}`)
    }
    addTextWithHighlight(boldMatch[1], true, `b${boldMatch.index}`)
    idx = boldMatch.index + boldMatch[0].length
  }
  if (idx < text.length) {
    addTextWithHighlight(text.slice(idx), false, `t${idx}`)
  }
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
  onFollowUp,
  screenshotUrl,
  audioUrl,
  onRegenerateMedia,
  isRegeneratingMedia,
  hasMediaTimecodes,
  isAudioPlaying,
  onPlayAudio,
  onStopAudio,
}: CandidateCardV2Props) {
  const { theme } = useTheme()
  const [showInfo, setShowInfo] = useState(false)
  const [showFollowUp, setShowFollowUp] = useState(false)
  const [showFreeInput, setShowFreeInput] = useState(false)
  const [freeText, setFreeText] = useState('')
  const followUpRef = useRef<HTMLDivElement>(null)

  const toggleAudio = (url: string) => {
    if (isAudioPlaying) {
      onStopAudio()
    } else {
      onPlayAudio(url)
    }
  }

  const handleMark = async (status: CandidateStatus) => {
    const next: CandidateStatus = candidate.status === status ? 'pending' : status
    await onMark(candidate.id, next)
  }

  // Derive media URLs from candidate.media (preferred), fall back to mediaMap props
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
  const showMediaColumn = !!(
    finalShot || finalAudio
    || mediaStatus === 'queued' || mediaStatus === 'running' || mediaStatus === 'failed'
  )

  const cefrPillColor = CEFR_PILL_COLOR[candidate.cefr_level ?? ''] ?? CEFR_PILL_DEFAULT

  const cardContent = (
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
        padding: '14px',
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
          background: 'var(--grad)',
          position: 'absolute',
          left: 0,
          top: 0,
        }} />
      )}

      {/* TOP BAR: toolbar (left) + Learn/Know/Skip (right) */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '8px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {onGenerateMeaning && !candidate.meaning?.meaning && (
            <ToolbarButton
              onClick={() => onGenerateMeaning(candidate.id)}
              disabled={isGenerating}
              ariaLabel="Generate meaning with AI"
              title="Generate meaning with AI"
            >
              {isGenerating ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
            </ToolbarButton>
          )}
          {onGenerateMeaning && candidate.meaning?.meaning && (
            <div
              className="relative"
              ref={followUpRef}
              onMouseLeave={() => { setShowFollowUp(false); setShowFreeInput(false) }}
            >
              <ToolbarButton
                onClick={() => setShowFollowUp((v) => !v)}
                disabled={isGenerating}
                ariaLabel="AI actions"
                title="Regenerate or ask a follow-up"
                className="w-9"
              >
                {isGenerating
                  ? <Loader2 size={13} className="animate-spin" />
                  : <><Sparkles size={12} /><ChevronDown size={9} style={{ marginLeft: '3px' }} /></>
                }
              </ToolbarButton>
              {showFollowUp && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  zIndex: 50,
                  paddingTop: '4px',
                }}>
                <div style={{
                  background: 'var(--surface-menu)',
                  border: '1px solid rgba(255,255,255,0.12)',
                  borderRadius: '8px',
                  padding: '4px 0',
                  minWidth: '180px',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
                }}>
                  <button
                    onClick={() => {
                      onGenerateMeaning(candidate.id)
                      setShowFollowUp(false)
                    }}
                    className="w-full text-left px-3 py-1.5 text-xs hover:bg-white/[0.08] cursor-pointer transition-colors"
                    style={{ color: 'var(--text-muted-light)' }}
                  >
                    Regenerate all
                  </button>
                  <div style={{ height: '1px', background: 'rgba(255,255,255,0.08)', margin: '4px 0' }} />
                  {onFollowUp && FOLLOW_UP_PRESETS.map((preset) => (
                    <button
                      key={preset.action}
                      onClick={() => {
                        onFollowUp(candidate.id, preset.action)
                        setShowFollowUp(false)
                      }}
                      className="w-full text-left px-3 py-1.5 text-xs hover:bg-white/[0.08] cursor-pointer transition-colors"
                      style={{ color: 'var(--text-muted-light)' }}
                    >
                      {preset.label}
                    </button>
                  ))}
                  {onFollowUp && (
                    <>
                      <div style={{ height: '1px', background: 'rgba(255,255,255,0.08)', margin: '4px 0' }} />
                      {showFreeInput ? (
                        <div className="px-3 py-1.5 flex gap-1">
                          <input
                            type="text"
                            value={freeText}
                            onChange={(e) => setFreeText(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && freeText.trim()) {
                                onFollowUp(candidate.id, 'free_question', freeText.trim())
                                setFreeText('')
                                setShowFollowUp(false)
                                setShowFreeInput(false)
                              }
                            }}
                            placeholder="Your question..."
                            autoFocus
                            className="flex-1 px-2 py-1 rounded text-xs bg-white/[0.06] border border-white/[0.1] outline-none"
                            style={{ color: 'var(--text-muted-light)' }}
                          />
                        </div>
                      ) : (
                        <button
                          onClick={() => setShowFreeInput(true)}
                          className="w-full text-left px-3 py-1.5 text-xs hover:bg-white/[0.08] cursor-pointer transition-colors"
                          style={{ color: 'var(--tm)' }}
                        >
                          Ask a question...
                        </button>
                      )}
                    </>
                  )}
                </div>
                </div>
              )}
            </div>
          )}
          {onRegenerateMedia && hasMediaTimecodes && (
            <ToolbarButton
              onClick={() => onRegenerateMedia(candidate.id)}
              disabled={isRegeneratingMedia}
              ariaLabel="Generate media for this candidate"
              title="Generate screenshot and audio (uses current fragment boundaries)"
            >
              {isRegeneratingMedia ? <Loader2 size={13} className="animate-spin" /> : <Film size={13} />}
            </ToolbarButton>
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
                left: 0,
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
                  <span style={{ fontFamily: 'monospace', fontSize: '12px', color: 'var(--tm)' }}>
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {MARK_BUTTONS.map((btn) => {
            const isActive = candidate.status === btn.status
            const active = MARK_ACTIVE[btn.status]
            return (
              <button
                key={btn.status}
                onClick={() => void handleMark(btn.status)}
                className="cursor-pointer transition-colors"
                style={{
                  padding: '4px 14px',
                  borderRadius: 'var(--btn-radius)',
                  fontSize: '11px',
                  fontWeight: isActive ? 700 : 600,
                  border: `1px solid ${isActive ? active.border : btn.border}`,
                  background: isActive ? active.bg : btn.bg,
                  color: isActive ? active.color : btn.color,
                  lineHeight: 1.4,
                }}
              >
                {btn.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Divider between top bar and content */}
      <div style={{ height: '1px', background: 'rgba(255,255,255,0.06)', margin: '14px 0' }} />

      {/* BODY: media (optional) + text column */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
        {showMediaColumn && (
          <div style={{ flexShrink: 0, width: '160px' }}>
            {finalShot ? (
              <div style={{ position: 'relative', width: '160px', height: '90px' }}>
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
                {finalAudio && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleAudio(finalAudio)
                    }}
                    aria-label={isAudioPlaying ? 'Stop audio' : 'Play audio'}
                    title={isAudioPlaying ? 'Stop audio' : 'Play audio'}
                    style={{
                      position: 'absolute',
                      top: '6px',
                      right: '6px',
                      width: '28px',
                      height: '28px',
                      background: 'rgba(15,17,30,0.85)',
                      border: '1px solid rgba(129,140,248,0.4)',
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--accent)',
                      cursor: 'pointer',
                      backdropFilter: 'blur(4px)',
                    }}
                  >
                    {isAudioPlaying ? <Square size={12} fill="currentColor" /> : <Play size={12} fill="currentColor" />}
                  </button>
                )}
              </div>
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
                  <span style={{ color: 'var(--error)' }} title={candidate.media?.error ?? undefined}>
                    Failed
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {/* RIGHT: text column with floated CEFR pill */}
        <div style={{ flex: 1, minWidth: 0, position: 'relative' }}>
          {candidate.is_phrasal_verb ? (
            <span
              style={{
                float: 'right',
                margin: '-2px 0 4px 8px',
                padding: '2px 10px',
                background: 'rgba(124,58,237,0.18)',
                color: '#a78bfa',
                borderRadius: '999px',
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.03em',
              }}
            >
              phrasal
            </span>
          ) : candidate.cefr_level && (
            <span
              style={{
                float: 'right',
                margin: '-2px 0 4px 8px',
                padding: '2px 10px',
                background: cefrPillColor.bg,
                color: cefrPillColor.color,
                borderRadius: '999px',
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.03em',
              }}
            >
              {candidate.cefr_level}
            </span>
          )}

          <p data-context-fragment style={{
            // Compensate for line-box leading: with line-height 1.5 on a 17px font,
            // the visible cap-line of the first character sits ~9px below the line
            // box top. Without this offset the text appears lower than the image top.
            margin: '-9px 0 6px',
            fontSize: '17px',
            color: 'var(--text-highlight)',
            lineHeight: 1.5,
          }}>
            &ldquo;{highlightWord(candidate.context_fragment, candidate.lemma, candidate.surface_form)}&rdquo;
          </p>

          {candidate.meaning?.meaning ? (
            <div style={{ marginTop: '10px' }}>
              {candidate.meaning.meaning
                .split(/\n+/)
                .filter((p) => p.trim().length > 0)
                .map((para, i) =>
                  /^---+$/.test(para.trim()) ? (
                    <hr key={i} style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.08)', margin: '12px 0' }} />
                  ) : (
                    <p
                      key={i}
                      style={{
                        margin: i === 0 ? 0 : '8px 0 0',
                        fontSize: '15px',
                        lineHeight: 1.55,
                        color: 'var(--text-muted-light)',
                      }}
                    >
                      {renderMeaning(para, candidate.lemma, candidate.surface_form)}
                    </p>
                  ),
                )}
              {candidate.meaning.translation && (
                <div
                  style={{
                    marginTop: '10px',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '6px',
                    fontSize: '14px',
                    color: 'var(--text-muted-light)',
                    lineHeight: 1.5,
                  }}
                >
                  <Languages size={14} style={{ marginTop: '3px', flexShrink: 0, color: 'var(--tm)' }} />
                  <span>{candidate.meaning.translation}</span>
                </div>
              )}
              {candidate.meaning.synonyms && (
                <div
                  style={{
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '6px',
                    fontSize: '14px',
                    color: 'var(--text-muted-light)',
                    lineHeight: 1.5,
                  }}
                >
                  <BookOpen size={14} style={{ marginTop: '3px', flexShrink: 0, color: 'var(--tm)' }} />
                  <span>{candidate.meaning.synonyms}</span>
                </div>
              )}
              {candidate.meaning.ipa && (
                <div
                  style={{
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '6px',
                    fontSize: '14px',
                    color: 'var(--text-muted-light)',
                    lineHeight: 1.5,
                  }}
                >
                  <span style={{ fontSize: '13px', marginTop: '1px', flexShrink: 0, color: 'var(--tm)' }}>🔊</span>
                  <span style={{ fontFamily: 'monospace', fontSize: '13px' }}>{candidate.meaning.ipa}</span>
                </div>
              )}
              {candidate.meaning.examples && (
                <div
                  style={{
                    marginTop: '10px',
                    padding: '8px 12px',
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: '8px',
                    border: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  {candidate.meaning.examples
                    .split(/\n+/)
                    .filter((l) => l.trim().length > 0)
                    .map((line, i) => (
                      <p
                        key={i}
                        style={{
                          margin: i === 0 ? 0 : '4px 0 0',
                          fontSize: '13px',
                          lineHeight: 1.5,
                          color: 'var(--tm)',
                        }}
                      >
                        {renderMeaning(line, candidate.lemma, candidate.surface_form)}
                      </p>
                    ))}
                </div>
              )}
            </div>
          ) : candidate.meaning?.status === 'running' ? (
            <p style={{ margin: '10px 0 0', fontSize: '13px', color: 'var(--td)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Loader2 size={13} className="animate-spin" /> Generating...
            </p>
          ) : candidate.meaning?.status === 'queued' ? (
            <p style={{ margin: '10px 0 0', fontSize: '13px', color: 'var(--td)' }}>Queued</p>
          ) : candidate.meaning?.status === 'failed' ? (
            <p style={{ margin: '10px 0 0', fontSize: '13px', color: 'var(--error)' }} title={candidate.meaning.error ?? undefined}>
              Failed to generate
            </p>
          ) : candidate.meaning?.status === 'cancelled' ? (
            <p style={{ margin: '10px 0 0', fontSize: '13px', color: 'var(--td)' }}>Cancelled</p>
          ) : null}
        </div>
      </div>
    </div>
  )

  if (theme === 'liquid-glass') {
    return <LiquidGlass style={{ borderRadius: 'var(--card-radius)' }}>{cardContent}</LiquidGlass>
  }
  return cardContent
}
