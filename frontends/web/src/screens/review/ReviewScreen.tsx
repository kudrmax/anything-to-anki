import { useEffect, useState, type CSSProperties } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { backIn, backTo } from '@/lib/backLink'
import { exportPath, parseSetScope } from '@/lib/scope'
import { allowedInClozeMarkup, isToolAction, reviewAction, type ReviewAction } from '@/lib/hotkeys'
import { pastedPicture } from '@/lib/pastedPicture'
import { phraseListShownPref, sourceTextShownPref } from '@/lib/preferences'
import { Aside, Page, PageHeader } from '@/shell'
import { ArrowDownWideNarrow, ChevronLeft, ChevronRight, Ellipsis, FileText, List, ListChevronsDownUp, ListChevronsUpDown, PanelRightClose, PanelRightOpen, Sparkles, Upload } from 'lucide-react'
import { Banner, Button, Empty, Icon, IconButton, Menu, Progress, Spinner, Toast, type MenuItem } from '@/ui'
import { GenerateMenu } from './GenerateMenu'
import { generationItems } from './generationItems'
import { DecisionButtons } from './PhraseActions'
import { PhraseCard } from './PhraseCard'
import { PhraseRow } from './PhraseRow'
import { SelectionPopover } from './SelectionPopover'
import { SortMenu } from './SortMenu'
import { sortItems, sortLabel } from './sortItems'
import type { SelectedText, SelectionPoint } from './SourceText'
import { SourceTexts } from './SourceTexts'
import { audioUrlForCandidate, useReview } from './useReview'
import { useSwipe } from './useSwipe'
import { ReviewList } from './ReviewList'
import type { DecisionButton, ReviewRow, SetScope, SourceStatus } from '@/api/types'
import css from './review.module.css'

const DECISION: Partial<Record<ReviewAction, DecisionButton>> = { learn: 'learn', cloze: 'cloze', known: 'known', skip: 'skip' }
type PhoneView = 'card' | 'text' | 'list'

const SOURCES_PATH = '/'
/** Источник разобран (статус выводит backend): остальное — по желанию. */
const DONE = 'Done'
const REVIEWED: SourceStatus = 'reviewed'
/** Ссылка на конкретную карточку: с ней ревью открывается сразу на ней. */
const CANDIDATE_PARAM = 'candidate'
const SCOPE_PARAM = 'scope'

/** Ревью любого набора — источника, коллекции или всех: у каждого набора свой экземпляр экрана. */
export function ReviewScreen() {
  const [searchParams] = useSearchParams()
  const scope = parseSetScope(searchParams.get(SCOPE_PARAM))
  const requestedCandidate = searchParams.get(CANDIDATE_PARAM)
  return (
    <ReviewView
      key={String(scope)}
      scope={scope}
      requestedId={requestedCandidate === null ? null : Number(requestedCandidate)}
    />
  )
}

function ReviewView({ scope, requestedId }: { scope: SetScope; requestedId: number | null }) {
  const navigate = useNavigate()
  const location = useLocation()
  const sourcesPath = backIn(location.state, SOURCES_PATH)
  const review = useReview(scope, requestedId)
  const [selection, setSelection] = useState<{ selected: SelectedText; point: SelectionPoint } | null>(null)
  const [sourceTextShown, setSourceTextShown] = useState(() => sourceTextShownPref.read())
  const toggleSourceText = () => {
    sourceTextShownPref.write(!sourceTextShown)
    setSourceTextShown(!sourceTextShown)
  }
  const [phraseListShown, setPhraseListShown] = useState(() => phraseListShownPref.read())
  const togglePhraseList = () => {
    phraseListShownPref.write(!phraseListShown)
    setPhraseListShown(!phraseListShown)
  }

  const { current, counts, editing } = review
  const set = review.header
  // На телефоне карточка занимает экран, а текст источника и список открываются на её месте.
  const [phoneView, setPhoneView] = useState<PhoneView>('card')
  const togglePhoneView = (view: PhoneView) => setPhoneView(prev => (prev === view ? 'card' : view))
  const hasCards = review.state.totalRows > 0

  // На телефоне фразы листают свайпом по карточке: влево — следующая, вправо — предыдущая.
  const swipe = useSwipe(direction => void review.step(direction === 'left' ? 1 : -1))

  const { press, step, cancelEditing, clozeEditing } = review
  const toggleAudio = review.player.toggle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && editing && !selection) { cancelEditing(); return }
      const action = reviewAction(e)
      // Инструменты карточки слушает сама карточка.
      if (!action || isToolAction(action)) return
      // В разметке cloze карточка остаётся на месте; оценка сначала закрывает разметку.
      if (clozeEditing && !allowedInClozeMarkup(action)) return
      e.preventDefault()
      if (action === 'prev' || action === 'next') {
        void step(action === 'next' ? 1 : -1)
        return
      }
      if (!current) return
      if (action === 'audio') {
        const url = audioUrlForCandidate(current)
        if (url) toggleAudio(url)
        return
      }
      const button = current.state.buttons.find(b => b.button === DECISION[action])
      if (button) void press(current.phrase_id, button)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [current, editing, selection, press, step, cancelEditing, toggleAudio, clozeEditing])

  const { pasteImage } = review
  useEffect(() => {
    if (!current) return
    const onPaste = (e: ClipboardEvent) => {
      const picture = pastedPicture(e)
      if (!picture) return
      e.preventDefault()
      void pasteImage(current.phrase_id, picture)
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [current, pasteImage])

  if (review.loading) {
    return <Page immersive header={<PageHeader title="Review" back={sourcesPath} />}><Empty><Spinner /></Empty></Page>
  }
  if (review.gone || !set) {
    return <Page immersive header={<PageHeader title="Review" back={sourcesPath} />}><Empty>Nothing to review here.</Empty></Page>
  }

  const closeSelection = () => {
    setSelection(null)
    window.getSelection()?.removeAllRanges()
  }

  const { hasSourceText } = review

  // Правка границ фразы идёт по тексту источника — на телефоне показываем его.
  const view: PhoneView = editing ? 'text' : phoneView

  const showCard = (id: number) => {
    void review.goTo(id)
    setPhoneView('card')
  }

  const toggleSection = (row: ReviewRow) => {
    if (row.section !== null) void review.toggleSection(row.section, row.open ?? false)
  }

  const goToExport = () => navigate(exportPath(scope), { state: backTo(location.pathname + location.search) })
  // На телефоне всё редкое — в одном меню, чтобы шапка уместилась в строку.
  const phoneMenu: MenuItem[] = [
    { label: 'Export to Anki', icon: Upload, value: `${counts.learn}`, onSelect: goToExport },
    ...(hasSourceText ? [{ label: view === 'text' ? 'Hide source text' : 'Source text', icon: FileText, separated: true, onSelect: () => togglePhoneView('text') }] : []),
    { label: 'Sort', icon: ArrowDownWideNarrow, value: sortLabel(review.sortOrder), separated: !hasSourceText, items: sortItems(review.sortOrder, review.setSortOrder) },
    { label: 'Generate', icon: Sparkles, items: generationItems(review) },
  ]

  const header = (
    <PageHeader
      title={set.title}
      back={sourcesPath}
      metaWithActions
      meta={counts.total > 0 && (
        <>
          {/* Десктоп: прогресс — линия по нижнему краю вкладок, на всю ширину окна; видна краем глаза. */}
          <span className={css.windowProgress} style={{ '--p': `${Math.round(counts.progress * 100)}%` } as CSSProperties} />
          {set.status === REVIEWED ? DONE : `${counts.reviewed} / ${counts.total}`}
        </>
      )}
    >
      <div className={`${css.headerTools} ${css.desktopOnly}`}>
        {review.position !== null && (
          <div className={css.stepper}>
            <span className={css.position}>{review.position} / {review.state.totalCards}</span>
            <IconButton icon={ChevronLeft} label="Previous phrase" disabled={!review.canPrev} onClick={() => void step(-1)} />
            <IconButton icon={ChevronRight} label="Next phrase" disabled={!review.canNext} onClick={() => void step(1)} />
          </div>
        )}
        {hasCards && (
          <>
            <SortMenu value={review.sortOrder} onChange={review.setSortOrder} />
            <GenerateMenu review={review} />
            <IconButton
              icon={phraseListShown ? ListChevronsDownUp : ListChevronsUpDown}
              label={phraseListShown ? 'Hide phrase list' : 'Show phrase list'}
              onClick={togglePhraseList}
            />
          </>
        )}
        {hasSourceText && (
          <IconButton
            icon={sourceTextShown ? PanelRightOpen : PanelRightClose}
            label={sourceTextShown ? 'Hide source text' : 'Show source text'}
            onClick={toggleSourceText}
          />
        )}
      </div>
      <Button className={`${css.export} ${css.desktopOnly}`} title="Export cards to Anki" onClick={goToExport}>
        <Icon as={Upload} size="s" />Export <span className={css.exportCount}>{counts.learn}</span>
      </Button>
      {hasCards && (
        <div className={`${css.headerTools} ${css.phoneOnly}`}>
          <IconButton icon={List} label="All phrases" active={view === 'list'} onClick={() => togglePhoneView('list')} />
          <Menu items={phoneMenu} trigger={<IconButton icon={Ellipsis} label="More" />} />
        </div>
      )}
      {counts.total > 0 && <div className={css.phoneProgress}><Progress value={counts.progress} /></div>}
    </PageHeader>
  )

  const banner = editing && <Banner tone="warn" onDismiss={cancelEditing}>Select the new boundary for “{editing.lemma}” in the source text</Banner>

  const sourceText = (onWordClick: (id: number) => void) => hasSourceText && (
    <SourceTexts
      text={review.text}
      done={review.state.done}
      onLoad={review.loadText}
      ensureBlock={review.ensureBlock}
      focused={(editing ? review.state.cards.get(editing.candidateId) : current) ?? null}
      editingSourceId={editing?.sourceId ?? null}
      onWordClick={onWordClick}
      onTextSelected={(selected, point) => setSelection({ selected, point })}
    />
  )

  const aside = hasSourceText && (
    <Aside>{sourceText(id => void review.goTo(id))}</Aside>
  )

  return (
    <Page fit wide immersive header={header} aside={aside || undefined} asideHidden={!sourceTextShown} banner={banner || undefined}>
      <div className={phraseListShown ? css.body : `${css.body} ${css.focus}`}>
        {!hasCards && <Empty>No candidates found.</Empty>}
        {view === 'text' && hasSourceText && <div className={css.textPanel}>{sourceText(showCard)}</div>}
        {view === 'list' && (
          <ReviewList
            className={css.listPanel}
            state={review.state}
            onLoad={review.loadRows}
            onToggleSection={toggleSection}
            renderCard={(card, isCurrent) => <PhraseRow key={card.phrase_id} candidate={card} current={isCurrent} onSelect={showCard} />}
            followKey={view}
          />
        )}
        <ReviewList
          className={view === 'card' ? css.queue : `${css.queue} ${css.away}`}
          {...swipe}
          state={review.state}
          onLoad={review.loadRows}
          onToggleSection={toggleSection}
          renderCard={(card, isCurrent) => isCurrent
            ? <PhraseCard key={card.phrase_id} candidate={card} review={review} />
            : <PhraseRow key={card.phrase_id} candidate={card} onSelect={id => void review.goTo(id)} />}
          followKey={phraseListShown}
        />
        {/* Телефон: решения — в панели под карточкой. В разметке cloze у панели свои Cancel и Save. */}
        {current && view === 'card' && !clozeEditing && (
          <div className={`${css.dock} ${css.phoneOnly}`}>
            <DecisionButtons candidate={current} review={review} />
          </div>
        )}
      </div>
      {selection && (
        <SelectionPopover
          phrase={selection.selected.text}
          point={selection.point}
          editing={editing}
          onSetBoundary={async () => { if (await review.setBoundary(selection.selected.selection)) setSelection(null) }}
          onAddWord={async targetWords => { if (await review.addWord(targetWords, selection.selected)) setSelection(null) }}
          onCancel={closeSelection}
        />
      )}
      <Toast message={review.toast} />
    </Page>
  )
}
