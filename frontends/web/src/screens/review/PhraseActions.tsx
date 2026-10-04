import { useState } from 'react'
import { ArrowRight, Feather, Flag, Image, ImagePlus, List, MessageCircle, Pencil, RefreshCw, Sparkles, Speech, X, ZoomIn, type LucideIcon } from 'lucide-react'
import type { CandidateStatus, FollowUpAction, StoredCandidate } from '@/api/types'
import { decisionChange, type Decision } from '@/lib/decision'
import { Button, Field, IconButton, Menu, type MenuItem } from '@/ui'
import { ImagePicker } from './ImagePicker'
import { PolishedPhrase } from './PolishedPhrase'
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

export function PhraseTools({ candidate, review }: PhraseActionsProps) {
  const [question, setQuestion] = useState('')
  const [complaint, setComplaint] = useState('')
  const [reasons, setReasons] = useState<string[]>([])
  const [pickingImage, setPickingImage] = useState(false)
  const id = candidate.id
  const isRated = candidate.status !== 'pending'
  const isVideo = review.source?.content_type === 'video'
  const isEditing = review.editing?.candidateId === id

  const followUpItems: MenuItem[] = [
    { label: 'Regenerate all', icon: RefreshCw, onSelect: () => void review.generate(id) },
    ...(isRated ? [] : [{
      label: 'Ask AI',
      icon: Sparkles,
      items: FOLLOW_UP_PRESETS.map(preset => ({ label: preset.label, icon: preset.icon, onSelect: () => void review.generate(id, preset.action) })),
    }]),
  ]
  const askQuestion = (close: () => void) => {
    if (!question.trim()) return
    void review.generate(id, 'free_question', question.trim())
    setQuestion('')
    close()
  }

  const toggleReason = (reason: string) =>
    setReasons(prev => (prev.includes(reason) ? prev.filter(r => r !== reason) : [...prev, reason]))
  const reportItems: MenuItem[] = review.reportReasons.map(reason => ({
    label: reason,
    selected: reasons.includes(reason),
    keepOpen: true,
    onSelect: () => toggleReason(reason),
  }))
  const canSend = reasons.length > 0 || complaint.trim().length > 0
  const sendReport = async (close: () => void) => {
    if (!canSend) return
    if (await review.report(id, reasons, complaint.trim())) {
      setReasons([])
      setComplaint('')
      close()
    }
  }

  return (
    <div className={css.tools}>
      {candidate.meaning?.meaning && (
        <Menu
          trigger={<IconButton icon={Sparkles} label="Regenerate or ask" busy={review.busy.generating.has(id)} />}
          items={followUpItems}
          footer={isRated ? undefined : close => (
            <div className={css.ask}>
              <Field
                value={question}
                placeholder="Ask your own question…"
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') askQuestion(close) }}
              />
              <IconButton icon={ArrowRight} label="Ask" disabled={!question.trim()} onClick={() => askQuestion(close)} />
            </div>
          )}
        />
      )}
      {isVideo && <IconButton icon={Image} label="Regenerate media" busy={review.busy.media.has(id)} onClick={() => void review.regenerateMedia(id)} />}
      {candidate.can_have_target_image && (
        <IconButton icon={ImagePlus} label="Find a picture of the word" busy={review.busy.image.has(id)} onClick={() => setPickingImage(true)} />
      )}
      {pickingImage && <ImagePicker candidate={candidate} review={review} onClose={() => setPickingImage(false)} />}
      <IconButton icon={Speech} label="Generate TTS audio" busy={review.busy.tts.has(id)} onClick={() => void review.generateTTS(id)} />
      <PolishedPhrase candidate={candidate} review={review} />
      <Menu
        trigger={<IconButton icon={Flag} label={candidate.reported ? 'Reported — report another problem' : 'Report a problem with this card'} className={candidate.reported ? css.reported : undefined} />}
        items={reportItems}
        footer={close => (
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
        )}
      />
      {isEditing
        ? <IconButton icon={X} label="Cancel editing" active onClick={review.cancelEditing} />
        : <IconButton icon={Pencil} label="Edit context fragment" onClick={() => review.startEditing(id)} />}
    </div>
  )
}
