import { useState, type CSSProperties } from 'react'
import { Brackets, Check, ChevronDown, ChevronUp } from 'lucide-react'
import type { CandidateCloze, CardLayoutView, DecisionButton, PhraseOrigin, StoredCandidate } from '@/api/types'
import { columnTracks, shownColumns, useCardLayoutEditing, type CardBlockContext } from '@/cardLayout'
import { CLOZE_HINT_LABEL } from '@/lib/clozeHints'
import { usePhone } from '@/lib/device'
import { Icon, Kbd } from '@/ui'
import { CardBody } from './CardBody'
import { CardPhrase } from './CardPhrase'
import { CefrTooltip } from './CefrTooltip'
import { DECISION_LABEL } from './decisionLabel'
import { ClozePanel } from './ClozePanel'
import { DecisionButtons, PhraseTools } from './PhraseActions'
import { PictureSuggestions } from './PictureSuggestions'
import type { PictureSuggestionsLoader } from './usePictureSuggestions'
import { audioUrlForCandidate, type Review } from './useReview'
import { useClozeEditor } from './useClozeEditor'
import { useDecisionSwipe } from './useDecisionSwipe'
import { usePhraseEditor } from './usePhraseEditor'
import { TargetPanel } from './TargetPanel'
import { useTargetEditor } from './useTargetEditor'
import { SWIPE_DECISION, type SwipeDirection } from './swipeDecision'
import { VIEW_CONTROL } from './viewControl'
import css from './review.module.css'

interface PhraseCardProps {
  candidate: StoredCandidate
  review: Review
  /** Раскладка тела карточки; null — ещё не загрузилась. */
  layout: CardLayoutView | null
  /** Нет — подсказки картинок выключены. */
  suggestPictures: PictureSuggestionsLoader | null
}

const GENERATED_PHRASE = 'generated phrase'
const SWIPE_DIRECTIONS: SwipeDirection[] = ['right', 'left', 'down']
/** Цифры решений видны на кнопках, здесь — только неочевидные клавиши. */
const KEY_HINTS: { keys: string[]; action: string }[] = [
  { keys: ['↑↓', '←→'], action: 'phrases' },
  { keys: ['Space'], action: 'learn' },
  { keys: ['⌘V'], action: 'paste a picture' },
]

/** Подпись нажатой кнопки рядом с фразой; какая нажата, решает backend. */
const DECIDED_LABEL: Record<DecisionButton, string> = { learn: 'Learn', cloze: 'Cloze', known: 'Known', skip: 'Skipped' }

/** Откуда фраза кандидата темы: из другого источника или сгенерирована. */
const originLabel = (origin: PhraseOrigin): string =>
  origin.kind === 'source' && origin.source_title ? `from ${origin.source_title}` : GENERATED_PHRASE

const clozeHint = ({ hint_kind }: CandidateCloze): string =>
  hint_kind === 'none' ? 'no hint' : `hint: ${CLOZE_HINT_LABEL[hint_kind].toLowerCase()}`

/**
 * Текущая фраза: сверху фраза, под ней тело по раскладке пользователя, снизу решения, факты и инструменты.
 */
export function PhraseCard({ candidate, review, layout, suggestPictures }: PhraseCardProps) {
  const [cefrAnchor, setCefrAnchor] = useState<HTMLElement | null>(null)
  // Телефон: карточка свёрнута в экран, Show all раскрывает её целиком — со справкой и инструментами.
  const [showAll, setShowAll] = useState(false)
  const phraseEditor = usePhraseEditor(candidate, review)
  const clozeEditor = useClozeEditor(candidate, review)
  const targetEditor = useTargetEditor(candidate, review)
  // Правка текста, разметка cloze и выбор таргета не открываются вместе: номера слов относятся к старому тексту.
  const editPhrase = () => {
    clozeEditor.cancel()
    targetEditor.cancel()
    phraseEditor.start()
  }
  const changeTarget = () => {
    phraseEditor.cancel()
    targetEditor.start()
  }
  const marking = clozeEditor.active || targetEditor.active
  const decided = candidate.state.buttons.find(button => button.pressed)?.button ?? null
  const editing = useCardLayoutEditing()
  const media = review.mediaFor(candidate)

  const phone = usePhone()
  const swipeButton = (direction: SwipeDirection) => candidate.state.buttons.find(b => b.button === SWIPE_DECISION[direction])
  // Уже принятое решение свайп не снимает, а оставляет и ведёт к следующей карточке.
  const swipeRef = useDecisionSwipe({
    enabled: phone && !marking && phraseEditor.draft === null && !editing,
    vertical: !showAll,
    canSwipe: direction => {
      const button = swipeButton(direction)
      return button !== undefined && button.command !== null && (!button.pressed || review.canNext)
    },
    onSwipe: async direction => {
      const button = swipeButton(direction)
      if (!button) return
      if (button.pressed) await review.step(1)
      else await review.press(candidate.phrase_id, button)
    },
  })

  const ctx: CardBlockContext = {
    candidate,
    media,
    playingUrl: review.player.playingUrl,
    togglePlay: review.player.toggle,
    keyAudioUrl: audioUrlForCandidate(candidate),
    generating: review.busy.generating.has(candidate.phrase_id),
    generate: () => void review.generate(candidate.phrase_id),
    useExample: line => void review.replaceWithExample(candidate.phrase_id, line),
    pictureSuggestions: suggestPictures && <PictureSuggestions candidate={candidate} review={review} load={suggestPictures} />,
    showCefr: setCefrAnchor,
  }
  // Пустые колонки видны, только пока в редакторе раскладки тянут блок: в них есть куда бросить.
  const columns = layout ? shownColumns(layout, ctx, editing?.dragged != null) : null

  return (
    <div className={css.cardBlock} ref={swipeRef}>
      {SWIPE_DIRECTIONS.map(direction => (
        <span key={direction} className={css.swipeStamp} data-stamp={direction} aria-hidden>{DECISION_LABEL[SWIPE_DECISION[direction]]}</span>
      ))}
      <article
        className={[css.card, marking && css.clozeEditing, !showAll && css.folded].filter(Boolean).join(' ')}
        data-candidate-id={candidate.phrase_id}
        style={{ '--card-cols': columns ? columnTracks(columns) : undefined } as CSSProperties}
      >
        <header className={css.cardHead}>
          <div className={css.phraseRow}>
            <CardPhrase candidate={candidate} editor={phraseEditor} cloze={clozeEditor} target={targetEditor} />
            {decided && (
              <span className={css.decided}><Icon as={Check} size="s" />{DECIDED_LABEL[decided]}</span>
            )}
          </div>
          {clozeEditor.active && <ClozePanel editor={clozeEditor} />}
          {targetEditor.active && <TargetPanel editor={targetEditor} />}
        </header>

        {layout && columns && <CardBody view={layout} columns={columns} showAll={showAll} />}
        <button type="button" className={css.showAll} aria-expanded={showAll} {...VIEW_CONTROL} onClick={() => setShowAll(open => !open)}>
          {showAll ? 'Show less' : 'Show all'}<Icon as={showAll ? ChevronUp : ChevronDown} size="s" />
        </button>

        <footer className={showAll ? css.cardFoot : `${css.cardFoot} ${css.collapsed}`}>
          {/* Десктоп: решения — в нижней полосе карточки; на телефоне они в панели под карточкой. */}
          <div className={css.footDecisions}>
            <DecisionButtons candidate={candidate} review={review} />
          </div>
          {/* Не влезает рядом с решениями — переносится под них. */}
          <div className={css.footRest}>
            <div className={css.facts}>
              {candidate.cloze && (
                <>
                  <span className={css.clozeFact}><Icon as={Brackets} size="s" />cloze</span>
                  <span>{clozeHint(candidate.cloze)}</span>
                </>
              )}
              {candidate.origin && <span>{originLabel(candidate.origin)}</span>}
            </div>
            <PhraseTools candidate={candidate} review={review} onEditPhrase={editPhrase} onChangeTarget={changeTarget} />
          </div>
        </footer>

        {cefrAnchor && candidate.cefr_breakdown && candidate.cefr_level && (
          <CefrTooltip breakdown={candidate.cefr_breakdown} cefrLevel={candidate.cefr_level} anchor={cefrAnchor} onClose={() => setCefrAnchor(null)} />
        )}
      </article>
      {/* Клавиши без своей кнопки — под карточкой, а не в ней. */}
      <p className={css.keysHint}>
        {KEY_HINTS.map(hint => (
          <span key={hint.action} className={css.keyHint}>
            {hint.keys.map(key => <Kbd key={key}>{key}</Kbd>)}
            {hint.action}
          </span>
        ))}
      </p>
    </div>
  )
}
