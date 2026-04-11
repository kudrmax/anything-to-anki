import { useRef, useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { BookOpen, ChevronDown, Film, Languages, Loader2, Pencil, Play, Sparkles, Square, Target, Volume2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CandidateStatus, FollowUpAction, StoredCandidate } from '@/api/types'
import { FONT_BODY, FONT_TARGET, FONT_ACTION, FONT_LEVEL } from '@/lib/design-tokens'

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


const STATUS_BORDER: Partial<Record<CandidateStatus, React.CSSProperties>> = {
  learn: { borderLeft: '2px solid var(--status-learn)' },
  known: { borderLeft: '2px solid var(--status-know)' },
  skip:  { borderLeft: '2px solid var(--status-skip)' },
}

const STATUS_BG: Partial<Record<CandidateStatus, string>> = {
  learn: 'var(--status-learn-bg)',
  known: 'var(--status-know-bg)',
  skip:  'var(--status-skip-bg)',
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
  A1: { bg: 'var(--hl-a1-bg)',  color: 'var(--hl-a1-text)' },
  A2: { bg: 'var(--hl-a2-bg)',  color: 'var(--hl-a2-text)' },
  B1: { bg: 'var(--hl-b1-bg)',  color: 'var(--hl-b1-text)' },
  B2: { bg: 'var(--hl-b2-bg)',  color: 'var(--hl-b2-text)' },
  C1: { bg: 'var(--hl-c1-bg)',  color: 'var(--hl-c1-text)' },
  C2: { bg: 'var(--hl-c2-bg)',  color: 'var(--hl-c2-text)' },
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
        fontSize: FONT_TARGET,
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

function FollowUpDropdown({ anchorEl, onClose, onRegenerate, onFollowUp, showFreeInput, setShowFreeInput, freeText, setFreeText }: {
  anchorEl: HTMLElement
  onClose: () => void
  onRegenerate: () => void
  onFollowUp?: (action: FollowUpAction, text?: string) => void
  showFreeInput: boolean
  setShowFreeInput: (v: boolean) => void
  freeText: string
  setFreeText: (v: string) => void
}) {
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const rect = anchorEl.getBoundingClientRect()
    setPos({ top: rect.bottom + 4, left: rect.left })
  }, [anchorEl])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node) && !anchorEl.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [anchorEl, onClose])

  return (
    <div ref={dropdownRef} className="glass-card glass-dropdown" style={{
      position: 'fixed',
      top: pos.top,
      left: pos.left,
      zIndex: 9999,
      borderRadius: '12px',
      padding: '4px 0',
      minWidth: '180px',
    }}>
      <button
        onClick={onRegenerate}
        className="w-full text-left px-3 py-1.5 text-xs hover:bg-white/[0.08] cursor-pointer transition-colors"
        style={{ color: 'var(--text-muted-light)' }}
      >
        Regenerate all
      </button>
      <div style={{ height: '1px', background: 'var(--surface-divider)', margin: '4px 0' }} />
      {onFollowUp && FOLLOW_UP_PRESETS.map((preset) => (
        <button
          key={preset.action}
          onClick={() => onFollowUp(preset.action)}
          className="w-full text-left px-3 py-1.5 text-xs hover:bg-white/[0.08] cursor-pointer transition-colors"
          style={{ color: 'var(--text-muted-light)' }}
        >
          {preset.label}
        </button>
      ))}
      {onFollowUp && (
        <>
          <div style={{ height: '1px', background: 'var(--surface-divider)', margin: '4px 0' }} />
          {showFreeInput ? (
            <div className="px-3 py-1.5 flex gap-1">
              <input
                type="text"
                value={freeText}
                onChange={(e) => setFreeText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && freeText.trim()) {
                    onFollowUp('free_question', freeText.trim())
                    setFreeText('')
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
  )
}

const TOOLBAR_BTN_CLS = 'glass-pill cursor-pointer'

const TOOLBAR_BTN_STYLE: React.CSSProperties = {
  padding: '4px',
  height: '28px',
  width: '28px',
  justifyContent: 'center',
  color: 'var(--td)',
}

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
      style={TOOLBAR_BTN_STYLE}
    >
      {children}
    </button>
  )
}

export function CandidateCardV2({
  candidate,
  sourceId,
  isHovered: _isHovered,
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
      )}
      style={{
        position: 'relative',
        padding: '20px',
        ...(isRated && STATUS_BORDER[candidate.status]),
        ...(isRated && {
          background: STATUS_BG[candidate.status] ?? 'rgba(148,163,184,0.07)',
          backdropFilter: 'none',
          WebkitBackdropFilter: 'none',
        }),
        ...(isEditingFragment
          ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 1px var(--accent)' }
          : {}),
      }}
    >

      {/* TOP BAR: toolbar (left) + Learn/Know/Skip (right) */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '8px',
        position: 'relative',
        zIndex: 10,
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
            <div className="relative" ref={followUpRef}>
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
              {showFollowUp && followUpRef.current && createPortal(
                <FollowUpDropdown
                  anchorEl={followUpRef.current}
                  onClose={() => { setShowFollowUp(false); setShowFreeInput(false) }}
                  onRegenerate={() => { onGenerateMeaning(candidate.id); setShowFollowUp(false) }}
                  onFollowUp={onFollowUp ? (action, text) => { onFollowUp(candidate.id, action, text); setShowFollowUp(false) } : undefined}
                  showFreeInput={showFreeInput}
                  setShowFreeInput={setShowFreeInput}
                  freeText={freeText}
                  setFreeText={setFreeText}
                />,
                document.body,
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
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {MARK_BUTTONS.map((btn) => {
            const isActive = candidate.status === btn.status
            const active = MARK_ACTIVE[btn.status]
            return (
              <button
                key={btn.status}
                onClick={() => void handleMark(btn.status)}
                className="glass-pill cursor-pointer transition-colors"
                style={{
                  padding: '4px 14px',
                  fontSize: FONT_ACTION,
                  fontWeight: isActive ? 700 : 600,
                  border: `0.5px solid ${isActive ? active.border : btn.border}`,
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
      <div style={{ height: '1px', background: 'var(--surface-divider)', margin: '14px 0' }} />

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
                    className="glass-pill"
                    style={{
                      position: 'absolute',
                      top: '6px',
                      right: '6px',
                      width: '28px',
                      height: '28px',
                      padding: '4px',
                      justifyContent: 'center',
                      border: '1px solid var(--accent)',
                      color: 'var(--accent)',
                      cursor: 'pointer',
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
                fontSize: FONT_ACTION,
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
                background: 'var(--hl-phrasal-bg)',
                color: 'var(--hl-phrasal-text)',
                borderRadius: '999px',
                fontSize: FONT_LEVEL,
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
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              {candidate.is_sweet_spot && (
                <Target size={12} style={{ color: 'var(--accent)' }} />
              )}
              <span style={{
                padding: '2px 10px',
                background: cefrPillColor.bg,
                color: cefrPillColor.color,
                borderRadius: '999px',
                fontSize: FONT_LEVEL,
                fontWeight: 700,
                letterSpacing: '0.03em',
              }}>
                {candidate.cefr_level}
              </span>
            </span>
          )}

          <p data-context-fragment style={{
            // Compensate for line-box leading: with line-height 1.5 on a 17px font,
            // the visible cap-line of the first character sits ~9px below the line
            // box top. Without this offset the text appears lower than the image top.
            margin: '-9px 0 6px',
            fontSize: FONT_BODY,
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
                    <hr key={i} style={{ border: 'none', borderTop: '1px solid var(--surface-divider)', margin: '12px 0' }} />
                  ) : (
                    <p
                      key={i}
                      style={{
                        margin: i === 0 ? 0 : '8px 0 0',
                        fontSize: FONT_BODY,
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
                    fontSize: FONT_BODY,
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
                    fontSize: FONT_BODY,
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
                    fontSize: FONT_BODY,
                    color: 'var(--text-muted-light)',
                    lineHeight: 1.5,
                  }}
                >
                  <Volume2 size={13} style={{ flexShrink: 0, color: 'var(--tm)' }} />
                  <span style={{ fontFamily: 'monospace', fontSize: '13px' }}>{candidate.meaning.ipa}</span>
                </div>
              )}
              {candidate.meaning.examples && (
                <div
                  style={{
                    marginTop: '10px',
                    padding: '8px 12px',
                    background: 'var(--glass)',
                    borderRadius: '8px',
                    border: '1px solid var(--glass-b)',
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
                          fontSize: FONT_BODY,
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
            <p style={{ margin: '10px 0 0', fontSize: FONT_BODY, color: 'var(--td)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Loader2 size={13} className="animate-spin" /> Generating...
            </p>
          ) : candidate.meaning?.status === 'queued' ? (
            <p style={{ margin: '10px 0 0', fontSize: FONT_BODY, color: 'var(--td)' }}>Queued</p>
          ) : candidate.meaning?.status === 'failed' ? (
            <p style={{ margin: '10px 0 0', fontSize: FONT_BODY, color: 'var(--error)' }} title={candidate.meaning.error ?? undefined}>
              Failed to generate
            </p>
          ) : candidate.meaning?.status === 'cancelled' ? (
            <p style={{ margin: '10px 0 0', fontSize: FONT_BODY, color: 'var(--td)' }}>Cancelled</p>
          ) : null}
        </div>
      </div>
    </div>
  )

  return cardContent
}
