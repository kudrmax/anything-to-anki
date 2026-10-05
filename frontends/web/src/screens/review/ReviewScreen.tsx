import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { decisionChange, learnConvertsCloze, type Decision } from '@/lib/decision'
import { allowedInClozeMarkup, reviewAction, type ReviewAction } from '@/lib/hotkeys'
import { pastedPicture } from '@/lib/pastedPicture'
import { phraseListShownPref, sourceTextShownPref } from '@/lib/preferences'
import { Aside, Page, PageHeader } from '@/shell'
import { ChevronLeft, ChevronRight, FileText, List, ListChevronsDownUp, ListChevronsUpDown, PanelRightClose, PanelRightOpen, Upload } from 'lucide-react'
import { Banner, Button, Empty, Icon, IconButton, Progress, Spinner, Toast } from '@/ui'
import { GenerateMenu } from './GenerateMenu'
import { PhraseCard } from './PhraseCard'
import { PhraseRow } from './PhraseRow'
import { SelectionPopover } from './SelectionPopover'
import { SortMenu } from './SortMenu'
import { SourceText, type SelectionPoint } from './SourceText'
import { audioUrlForCandidate, useReview } from './useReview'
import { useShownCandidates } from './useShownCandidates'
import css from './review.module.css'

const DECISION: Partial<Record<ReviewAction, Decision>> = { learn: 'learn', known: 'known', skip: 'skip' }
type PhoneView = 'card' | 'text' | 'list'

const SOURCES_PATH = '/'
/** Ссылка на конкретную карточку: с ней ревью открывается сразу на ней. */
const CANDIDATE_PARAM = 'candidate'

export function ReviewScreen() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const requestedCandidate = searchParams.get(CANDIDATE_PARAM)
  const review = useReview(Number(id), requestedCandidate === null ? null : Number(requestedCandidate))
  const listRef = useRef<HTMLDivElement>(null)
  const [selection, setSelection] = useState<{ phrase: string; point: SelectionPoint } | null>(null)
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

  const { source, candidates, currentId, counts, editing } = review
  // На телефоне карточка занимает экран, а текст источника и список открываются на её месте.
  const [phoneView, setPhoneView] = useState<PhoneView>('card')
  const togglePhoneView = (view: PhoneView) => setPhoneView(prev => (prev === view ? 'card' : view))
  const current = candidates.find(c => c.id === currentId) ?? null
  const list = useShownCandidates(
    candidates,
    source?.initially_shown_candidates ?? null,
    currentId,
    `${id}:${review.sortOrder}`,
  )

  // Держим карточку в поле зрения: и когда список только появился (ревью открыли ссылкой на карточку),
  // и когда фоновое обновление переставило её в списке.
  const currentIndex = candidates.findIndex(c => c.id === currentId)
  const prevId = candidates[currentIndex - 1]?.id ?? null
  const nextId = currentIndex >= 0 ? candidates[currentIndex + 1]?.id ?? null : null
  const { loading } = review
  useEffect(() => {
    if (loading) return
    listRef.current?.querySelector(`[data-candidate-id="${currentId}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [currentId, currentIndex, loading])

  const { mark, setCurrentId, cancelEditing, sourceId, clozeEditing, startCloze, cancelCloze } = review
  const toggleAudio = review.player.toggle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && editing && !selection) { cancelEditing(); return }
      const action = reviewAction(e)
      if (!action) return
      // В разметке cloze карточка остаётся на месте; оценка сначала закрывает разметку.
      if (clozeEditing && !allowedInClozeMarkup(action)) return
      e.preventDefault()
      if (action === 'prev' || action === 'next') {
        const target = action === 'next' ? nextId : prevId
        if (target !== null) setCurrentId(target)
        return
      }
      if (!current) return
      if (action === 'audio') {
        const url = audioUrlForCandidate(current, sourceId)
        if (url) toggleAudio(url)
        return
      }
      if (action === 'cloze') {
        if (current.can_cloze) startCloze(current.id)
        return
      }
      const status = DECISION[action]
      if (!status) return
      if (clozeEditing) cancelCloze()
      void mark(current.id, decisionChange(current.status, status, learnConvertsCloze(current)))
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [current, prevId, nextId, editing, selection, mark, setCurrentId, cancelEditing, toggleAudio, sourceId, clozeEditing, startCloze, cancelCloze])

  const { pasteImage } = review
  useEffect(() => {
    if (!current) return
    const onPaste = (e: ClipboardEvent) => {
      const picture = pastedPicture(e)
      if (!picture) return
      e.preventDefault()
      void pasteImage(current.id, picture)
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [current, pasteImage])

  if (review.loading) {
    return <Page header={<PageHeader title="Review" back={SOURCES_PATH} />}><Empty><Spinner /></Empty></Page>
  }
  if (!source) {
    return <Page header={<PageHeader title="Review" back={SOURCES_PATH} />}><Empty>Source not found.</Empty></Page>
  }

  const closeSelection = () => {
    setSelection(null)
    window.getSelection()?.removeAllRanges()
  }

  const hasSourceText = source.has_source_text

  const showCard = (id: number) => {
    setCurrentId(id)
    setPhoneView('card')
  }

  // Позиция и ‹ › — в ряду телефона и в шапке десктопа без списка.
  const stepper = (
    <>
      <span className={css.position}>{currentIndex + 1} / {candidates.length}</span>
      <IconButton icon={ChevronLeft} label="Previous phrase" disabled={prevId === null} onClick={() => prevId !== null && showCard(prevId)} />
      <IconButton icon={ChevronRight} label="Next phrase" disabled={nextId === null} onClick={() => nextId !== null && showCard(nextId)} />
    </>
  )

  const header = (
    <PageHeader
      title={source.title}
      back={SOURCES_PATH}
      metaWithActions
      meta={candidates.length > 0 && (
        <>
          <Progress inline value={counts.progress} />
          {counts.marked} / {counts.total}
        </>
      )}
    >
      <div className={css.headerTools}>
        {candidates.length > 0 && !phraseListShown && <div className={css.headerStepper}>{stepper}</div>}
        {candidates.length > 0 && (
          <>
            <SortMenu value={review.sortOrder} onChange={review.setSortOrder} />
            <GenerateMenu review={review} />
          </>
        )}
        {candidates.length > 0 && (
          <IconButton
            className={css.desktopOnly}
            icon={phraseListShown ? ListChevronsDownUp : ListChevronsUpDown}
            label={phraseListShown ? 'Hide phrase list' : 'Show phrase list'}
            onClick={togglePhraseList}
          />
        )}
        {hasSourceText && (
          <IconButton
            className={css.desktopOnly}
            icon={sourceTextShown ? PanelRightOpen : PanelRightClose}
            label={sourceTextShown ? 'Hide source text' : 'Show source text'}
            onClick={toggleSourceText}
          />
        )}
      </div>
      <Button variant="fill" title="Export cards to Anki" onClick={() => navigate(`/sources/${sourceId}/export`)}>
        <Icon as={Upload} size="s" />{counts.learn}
      </Button>
    </PageHeader>
  )

  const banner = (
    <>
      {review.vpnBlocked && <Banner tone="warn" onDismiss={review.dismissVpn}>AI unavailable — turn on VPN</Banner>}
      {editing && <Banner tone="warn" onDismiss={cancelEditing}>Select the new boundary for “{editing.lemma}” in the source text</Banner>}
    </>
  )

  // Правка границ фразы идёт по тексту источника — на телефоне показываем его.
  const view: PhoneView = editing ? 'text' : phoneView

  const sourceText = (onWordClick: (id: number) => void) => (
    <SourceText
      text={source.cleaned_text ?? source.raw_text}
      candidates={candidates}
      focusId={editing?.candidateId ?? currentId}
      onWordClick={onWordClick}
      onTextSelected={(phrase, point) => setSelection({ phrase, point })}
    />
  )

  const aside = hasSourceText && (
    <Aside>{sourceText(setCurrentId)}</Aside>
  )

  return (
    <Page fit wide header={header} aside={aside || undefined} asideHidden={!sourceTextShown} banner={(review.vpnBlocked || editing) ? banner : undefined}>
      <div ref={listRef} className={phraseListShown ? css.body : `${css.body} ${css.focus}`}>
        {candidates.length === 0 && <Empty>No candidates found for this source.</Empty>}
        {candidates.length > 0 && (
          <div className={css.phoneBar}>
            {hasSourceText && <IconButton className={css.phoneOnly} icon={FileText} label="Source text" active={view === 'text'} onClick={() => togglePhoneView('text')} />}
            <IconButton className={css.phoneOnly} icon={List} label="All phrases" active={view === 'list'} onClick={() => togglePhoneView('list')} />
            {stepper}
          </div>
        )}
        {view === 'text' && hasSourceText && <div className={css.textPanel}>{sourceText(showCard)}</div>}
        {view === 'list' && (
          <div className={css.listPanel}>
            {list.shown.map(candidate => (
              <PhraseRow key={candidate.id} candidate={candidate} current={candidate.id === currentId} onSelect={showCard} />
            ))}
            {list.hiddenCount > 0 && (
              <Button variant="link" onClick={list.showMore}>Show {list.nextPageCount} more · {list.hiddenCount} left</Button>
            )}
          </div>
        )}
        <div className={view === 'card' ? css.queue : `${css.queue} ${css.away}`}>
          {list.shown.map(candidate => candidate.id === currentId
            ? <PhraseCard key={candidate.id} candidate={candidate} review={review} />
            : <PhraseRow key={candidate.id} candidate={candidate} onSelect={setCurrentId} />)}
        </div>
        {list.hiddenCount > 0 && (
          <div className={css.showMore}>
            <Button variant="link" onClick={list.showMore}>
              Show {list.nextPageCount} more · {list.hiddenCount} left
            </Button>
          </div>
        )}
        {candidates.length > 0 && counts.marked === counts.total && <Empty>All candidates reviewed.</Empty>}
        {candidates.length > 0 && (
          <div className={css.hint}>↑ ↓ — next phrase · 1 Learn · 2 Cloze · 3 Know · 4 Skip · Space — play audio · ⌘V — paste picture</div>
        )}
      </div>
      {selection && (
        <SelectionPopover
          phrase={selection.phrase}
          point={selection.point}
          editing={editing}
          onSetBoundary={async phrase => { if (await review.setBoundary(phrase)) setSelection(null) }}
          onAddWord={async (target, context) => { if (await review.addWord(target, context)) setSelection(null) }}
          onCancel={closeSelection}
        />
      )}
      <Toast message={review.toast} />
    </Page>
  )
}
