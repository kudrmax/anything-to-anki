import { useState } from 'react'
import { ArrowRight, Clapperboard, Feather, Flag, HelpCircle, ImagePlus, List, MessageCircle, Pencil, RefreshCw, Sparkles, Speech, TextCursorInput, TextSelect, WandSparkles, X, ZoomIn, type LucideIcon } from 'lucide-react'
import type { CandidateStatus, FollowUpAction, StoredCandidate } from '@/api/types'
import { decisionChange, type Decision } from '@/lib/decision'
import { Button, Field, Icon, IconButton, Menu, Spinner, type MenuItem, type MenuPage } from '@/ui'
import { ImagePicker } from './ImagePicker'
import { PolishComparison } from './PolishComparison'
import type { Review } from './useReview'
import css from './review.module.css'

const FOLLOW_UP_PRESETS: { action: FollowUpAction; label: string; icon: LucideIcon }[] = [
  { action: 'give_examples', label: 'Give examples', icon: List },
  { action: 'explain_detail', label: 'Explain in detail', icon: ZoomIn },
  { action: 'explain_simpler', label: 'Explain simpler', icon: Feather },
  { action: 'how_to_say', label: 'How to say it', icon: MessageCircle },
]

const DECISIONS: { status: Decision; label: string; kbd: string }[] = [
  { status: 'learn', label: 'Learn', kbd: '1' },
  { status: 'known', label: 'Know', kbd: '2' },
  { status: 'skip', label: 'Skip', kbd: '3' },
]

interface PhraseActionsProps {
  candidate: StoredCandidate
  review: Review
}

export function DecisionButtons({ candidate, review }: PhraseActionsProps) {
  const isRated = candidate.status !== 'pending'
  const decide = (status: Decision) => void review.mark(candidate.id, decisionChange(candidate.status, status))
  const isPrimary = (status: CandidateStatus) => (isRated ? candidate.status === status : status === 'learn')
  return (
    <div className={css.decisions}>
      {DECISIONS.map(decision => (
        <Button key={decision.status} variant={isPrimary(decision.status) ? 'fill' : 'soft'} kbd={decision.kbd} onClick={() => decide(decision.status)}>
          {decision.label}
        </Button>
      ))}
    </div>
  )
}

interface PhraseToolsProps extends PhraseActionsProps {
  onEditPhrase: () => void
}

export function PhraseTools({ candidate, review, onEditPhrase }: PhraseToolsProps) {
  const [question, setQuestion] = useState('')
  const [complaint, setComplaint] = useState('')
  const [reasons, setReasons] = useState<string[]>([])
  const [pickingImage, setPickingImage] = useState(false)
  const id = candidate.id
  const isRated = candidate.status !== 'pending'
  const isVideo = review.source?.content_type === 'video'
  const isEditing = review.editing?.candidateId === id
  const hasMeaning = Boolean(candidate.meaning?.meaning)
  const polishing = candidate.polish_status === 'queued' || candidate.polish_status === 'running'
  const busy = {
    meaning: review.busy.generating.has(id),
    media: review.busy.media.has(id),
    tts: review.busy.tts.has(id),
    image: review.busy.image.has(id),
  }

  const askQuestion = (close: () => void) => {
    if (!question.trim()) return
    void review.generate(id, 'free_question', question.trim())
    setQuestion('')
    close()
  }
  const askPage: MenuPage = {
    items: [],
    footer: close => (
      <div className={css.ask}>
        <Field
          autoFocus
          value={question}
          placeholder="Your own question…"
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') askQuestion(close) }}
        />
        <IconButton icon={ArrowRight} label="Ask" disabled={!question.trim()} onClick={() => askQuestion(close)} />
      </div>
    ),
  }

  const toggleReason = (reason: string) =>
    setReasons(prev => (prev.includes(reason) ? prev.filter(r => r !== reason) : [...prev, reason]))
  const canSend = reasons.length > 0 || complaint.trim().length > 0
  const sendReport = async (close: () => void) => {
    if (!canSend) return
    if (await review.report(id, reasons, complaint.trim())) {
      setReasons([])
      setComplaint('')
      close()
    }
  }
  const report: MenuPage = {
    items: review.reportReasons.map(reason => ({
      label: reason,
      selected: reasons.includes(reason),
      keepOpen: true,
      onSelect: () => toggleReason(reason),
    })),
    footer: close => (
      <div className={css.reportFooter}>
        <Field
          value={complaint}
          placeholder="Describe the problem…"
          onChange={e => setComplaint(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') void sendReport(close) }}
        />
        <Button variant="fill" wide disabled={!canSend} onClick={() => void sendReport(close)}>
          {reasons.length > 1 ? `Send ${reasons.length} reasons` : 'Send report'}
        </Button>
      </div>
    ),
  }

  const actionItem = (label: string, icon: LucideIcon, isBusy: boolean, onSelect: () => void, hint?: string): MenuItem => ({
    label,
    hint,
    icon,
    lead: isBusy ? <Spinner /> : undefined,
    disabled: isBusy,
    onSelect,
  })

  const editItems: MenuItem[] = [
    { label: 'Edit text', hint: 'Fix words in the phrase', icon: TextCursorInput, onSelect: onEditPhrase },
    { label: 'Change boundary', hint: 'Pick the phrase in the source', icon: TextSelect, onSelect: () => review.startEditing(id) },
  ]

  const meaningItems: MenuItem[] = [
    actionItem(hasMeaning ? 'Regenerate all' : 'Generate', RefreshCw, busy.meaning, () => void review.generate(id), 'Definition, translation, examples'),
    ...(hasMeaning && !isRated ? [
      ...FOLLOW_UP_PRESETS.map((preset, index) => ({
        label: preset.label,
        icon: preset.icon,
        disabled: busy.meaning,
        separated: index === 0,
        onSelect: () => void review.generate(id, preset.action),
      })),
      { label: 'Your own question', icon: HelpCircle, disabled: busy.meaning, page: askPage },
    ] : []),
  ]
  const meaningEntry: MenuItem = meaningItems.length === 1
    ? { ...meaningItems[0], label: 'Meaning' }
    : { label: 'Meaning', hint: 'From scratch or a single part', icon: Sparkles, lead: busy.meaning ? <Spinner /> : undefined, items: meaningItems }

  const polished = candidate.polished_fragment
  const polishEntry: MenuItem = polished && !polishing
    ? {
      label: 'Polish',
      hint: candidate.polish_reverted ? 'Original is in use — compare' : 'Compare, revert, polish again',
      icon: WandSparkles,
      page: { items: [], footer: close => <PolishComparison candidate={candidate} polished={polished} review={review} onDone={close} /> },
    }
    : actionItem('Polish', WandSparkles, polishing, () => void review.polishAgain(id), 'AI simplifies the phrase')

  const regenerateItems: MenuItem[] = [
    meaningEntry,
    ...(review.source?.can_polish_phrases || polished ? [polishEntry] : []),
    actionItem('Speech', Speech, busy.tts, () => void review.generateTTS(id), 'Phrase read aloud'),
    ...(isVideo ? [actionItem('Screenshot and clip', Clapperboard, busy.media, () => void review.regenerateMedia(id), 'From the video')] : []),
  ]
  const regenerating = busy.meaning || busy.media || busy.tts || polishing

  const menuTrigger = (icon: LucideIcon, label: string, isBusy: boolean, className?: string) => (
    <Button variant="link" className={[css.iconTrigger, className].filter(Boolean).join(' ')} title={label} aria-label={label}>
      {isBusy ? <Spinner /> : <Icon as={icon} />}
    </Button>
  )

  return (
    <div className={css.tools}>
      {isEditing && <IconButton icon={X} label="Cancel editing" active onClick={review.cancelEditing} />}
      <IconButton icon={ImagePlus} label="Choose a picture of the word" busy={busy.image} onClick={() => setPickingImage(true)} />
      <Menu items={editItems} trigger={menuTrigger(Pencil, 'Edit phrase', false)} />
      <Menu items={regenerateItems} trigger={menuTrigger(RefreshCw, 'Regenerate', regenerating)} />
      <Menu
        items={report.items}
        footer={report.footer}
        trigger={menuTrigger(
          Flag,
          candidate.reported ? 'Reported — report another problem' : 'Report a problem with this card',
          false,
          candidate.reported ? css.reported : undefined,
        )}
      />
      {pickingImage && <ImagePicker candidate={candidate} review={review} onClose={() => setPickingImage(false)} />}
    </div>
  )
}
