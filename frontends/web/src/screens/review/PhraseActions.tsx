import { useState } from 'react'
import { Flag, Image, Pencil, Sparkles, Speech, X } from 'lucide-react'
import type { CandidateStatus, FollowUpAction, StoredCandidate } from '@/api/types'
import { decisionChange, type Decision } from '@/lib/decision'
import { parseExamples } from '@/lib/text/meaning'
import { Button, Field, IconButton, Menu, type MenuItem } from '@/ui'
import type { Review } from './useReview'
import css from './review.module.css'

const FOLLOW_UP_PRESETS: { action: FollowUpAction; label: string }[] = [
  { action: 'give_examples', label: 'Give examples' },
  { action: 'explain_detail', label: 'Explain in detail' },
  { action: 'explain_simpler', label: 'Explain simpler' },
  { action: 'how_to_say', label: 'How to say it' },
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
  const id = candidate.id
  const isRated = candidate.status !== 'pending'
  const isVideo = review.source?.content_type === 'video'
  const isEditing = review.editing?.candidateId === id

  const followUpItems: MenuItem[] = [
    { label: 'Regenerate all', onSelect: () => void review.generate(id) },
    ...(isRated ? [] : FOLLOW_UP_PRESETS.map(preset => ({ label: preset.label, onSelect: () => void review.generate(id, preset.action) }))),
    ...parseExamples(candidate.meaning?.examples).map(example => ({
      label: `Replace phrase with: ${example}`,
      onSelect: () => void review.replaceWithExample(id, example),
    })),
  ]

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
            <Field
              value={question}
              placeholder="Ask a question…"
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => {
                if (e.key !== 'Enter' || !question.trim()) return
                void review.generate(id, 'free_question', question.trim())
                setQuestion('')
                close()
              }}
            />
          )}
        />
      )}
      {isVideo && <IconButton icon={Image} label="Regenerate media" busy={review.busy.media.has(id)} onClick={() => void review.regenerateMedia(id)} />}
      <IconButton icon={Speech} label="Generate TTS audio" busy={review.busy.tts.has(id)} onClick={() => void review.generateTTS(id)} />
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
