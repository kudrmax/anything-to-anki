import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Check, Clapperboard, Feather, Flag, HelpCircle, ImagePlus, List, MessageCircle, Pencil, RefreshCw, Sparkles, Speech, TextCursorInput, TextSelect, WandSparkles, X, ZoomIn, type LucideIcon } from 'lucide-react'
import type { ButtonCommand, CardButton, DecisionButton, FollowUpAction, StoredCandidate } from '@/api/types'
import { KEY_LABEL, OVERLAY, toolKey, type ToolAction } from '@/lib/hotkeys'
import { keepFocusOnMouseDown } from '@/lib/mouseFocus'
import { phraseWordTexts } from '@/lib/text/phraseParts'
import { toggled } from '@/lib/text/words'
import { Button, Field, Icon, IconButton, Menu, Spinner, Text, WordPicker, Kbd, type MenuHandle, type MenuItem, type MenuPage } from '@/ui'
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

const UNKNOWN_WORDS_HINT = 'Tap the words you don\'t know'

const BUTTON_LOOK: Record<DecisionButton, { label: string; kbd: string; primary: boolean }> = {
  learn: { label: 'Learn', kbd: KEY_LABEL.learn, primary: true },
  cloze: { label: 'Cloze', kbd: KEY_LABEL.cloze, primary: false },
  known: { label: 'Know', kbd: KEY_LABEL.known, primary: false },
  skip: { label: 'Skip', kbd: KEY_LABEL.skip, primary: false },
}

const OPENS_EDITOR: Record<ButtonCommand, boolean> = { edit_cloze: true, decide: false }

interface PhraseActionsProps {
  candidate: StoredCandidate
  review: Review
}

/**
 * Решения по фразе: Learn L · Cloze C · Know K · Skip S. Что делает кнопка и какая нажата, решает backend.
 * Learn залит всегда — это основное действие; нажатая кнопка отмечена галочкой.
 */
export function DecisionButtons({ candidate, review }: PhraseActionsProps) {
  const editing = review.clozeEditingId === candidate.phrase_id
  const variant = (button: CardButton) => (isFilled(button, editing, candidate.can_edit_cloze) ? 'fill' : 'soft')
  return (
    <div className={css.decisions}>
      {candidate.state.buttons.map(button => (
        <Button
          key={button.button}
          variant={variant(button)}
          className={button.pressed ? css.chosen : undefined}
          kbd={BUTTON_LOOK[button.button].kbd}
          disabled={button.command === null}
          onMouseDown={keepFocusOnMouseDown}
          onClick={() => void review.press(candidate.phrase_id, button)}
        >
          {button.pressed && <Icon as={Check} size="s" />}{BUTTON_LOOK[button.button].label}
        </Button>
      ))}
    </div>
  )
}

/**
 * Пока открыта разметка cloze, залита кнопка, которая её открыла, а у карточки-cloze — её нажатая кнопка;
 * иначе — основная. Всё это сказал backend: команда кнопки, нажата ли она, можно ли править cloze.
 */
const isFilled = (button: CardButton, editing: boolean, canEditCloze: boolean): boolean => {
  if (!editing) return BUTTON_LOOK[button.button].primary
  const opensEditor = button.command !== null && OPENS_EDITOR[button.command]
  return opensEditor || (button.pressed && canEditCloze)
}

interface PhraseToolsProps extends PhraseActionsProps {
  onEditPhrase: () => void
}

export function PhraseTools({ candidate, review, onEditPhrase }: PhraseToolsProps) {
  const [question, setQuestion] = useState('')
  const [complaint, setComplaint] = useState('')
  const [reasons, setReasons] = useState<string[]>([])
  const [unknownWords, setUnknownWords] = useState<Set<number>>(new Set())
  const [pickingImage, setPickingImage] = useState(false)
  const id = candidate.phrase_id
  const isRated = candidate.is_done
  const isVideo = candidate.source.has_video
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
  // Причина, под которой отмечают незнакомые слова фразы: слова выбираются, только пока она выбрана.
  const picksWords = review.reportReasons.some(reason => reason.picks_words && reasons.includes(reason.label))
  const pickedUnknown = picksWords ? [...unknownWords].sort((a, b) => a - b) : []
  const canSend = reasons.length > 0 || complaint.trim().length > 0
  const sendReport = async (close: () => void) => {
    if (!canSend) return
    if (await review.report(id, reasons, complaint.trim(), pickedUnknown)) {
      setReasons([])
      setComplaint('')
      setUnknownWords(new Set())
      close()
    }
  }
  const report: MenuPage = {
    items: review.reportReasons.map(reason => ({
      label: reason.label,
      selected: reasons.includes(reason.label),
      keepOpen: true,
      onSelect: () => toggleReason(reason.label),
    })),
    footer: close => (
      <div className={css.reportFooter}>
        {picksWords && (
          <>
            <Text tone="muted" size="s">{UNKNOWN_WORDS_HINT}</Text>
            <WordPicker words={phraseWordTexts(candidate.phrase)} selected={unknownWords} onToggle={i => setUnknownWords(prev => toggled(prev, i))} />
          </>
        )}
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

  const polished = candidate.polished_phrase?.text ?? null
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
    ...(candidate.source.can_polish_phrases || polished ? [polishEntry] : []),
    actionItem('Speech', Speech, busy.tts, () => void review.generateTTS(id), 'Phrase read aloud'),
    ...(isVideo ? [actionItem('Screenshot and clip', Clapperboard, busy.media, () => void review.regenerateMedia(id), 'From the video')] : []),
  ]
  const regenerating = busy.meaning || busy.media || busy.tts || polishing

  const editMenu = useRef<MenuHandle>(null)
  const regenerateMenu = useRef<MenuHandle>(null)
  const reportMenu = useRef<MenuHandle>(null)
  const markingCloze = review.clozeEditingId === id
  const imageBusy = busy.image
  useEffect(() => {
    const menus = { edit: editMenu, regenerate: regenerateMenu, report: reportMenu }
    const isOpen = (tool: ToolAction) => (tool === 'image' ? pickingImage : Boolean(menus[tool].current?.isOpen()))
    const toggle = (tool: ToolAction) => {
      if (tool === 'image') setPickingImage(open => !open && !imageBusy)
      else if (isOpen(tool)) menus[tool].current?.close()
      else menus[tool].current?.open()
    }
    const onKey = (e: KeyboardEvent) => {
      const tool = toolKey(e)
      // В разметке cloze инструменты карточки не открываются.
      if (!tool || markingCloze) return
      // Пока открыто меню или окно, клавиша закрывает только открытое ею же.
      if (document.querySelector(OVERLAY) && !isOpen(tool)) return
      e.preventDefault()
      toggle(tool)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [markingCloze, imageBusy, pickingImage])

  const menuTrigger = (icon: LucideIcon, label: string, action: ToolAction, isBusy: boolean, className?: string) => (
    <Button variant="link" className={[css.iconTrigger, className].filter(Boolean).join(' ')} title={label} aria-label={label}>
      {isBusy ? <Spinner /> : <Icon as={icon} />}
      <Kbd corner>{KEY_LABEL[action]}</Kbd>
    </Button>
  )

  return (
    <div className={css.tools}>
      {isEditing && <IconButton icon={X} label="Cancel editing" active onClick={review.cancelEditing} />}
      <IconButton icon={ImagePlus} label="Choose a picture of the word" kbd={KEY_LABEL.image} busy={busy.image} onClick={() => setPickingImage(true)} />
      <Menu ref={editMenu} items={editItems} trigger={menuTrigger(Pencil, 'Edit phrase', 'edit', false)} />
      <Menu ref={regenerateMenu} items={regenerateItems} trigger={menuTrigger(RefreshCw, 'Regenerate', 'regenerate', regenerating)} />
      <Menu
        ref={reportMenu}
        items={report.items}
        footer={report.footer}
        trigger={menuTrigger(
          Flag,
          candidate.reported ? 'Reported — report another problem' : 'Report a problem with this card',
          'report',
          false,
          candidate.reported ? css.reported : undefined,
        )}
      />
      {pickingImage && <ImagePicker candidate={candidate} review={review} onClose={() => setPickingImage(false)} />}
    </div>
  )
}
