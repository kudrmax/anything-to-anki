import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { backIn } from '@/lib/backLink'
import { allowedInClozeMarkup, reviewAction, type ReviewAction } from '@/lib/hotkeys'
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
import { SourceText, type SelectedText, type SelectionPoint } from './SourceText'
import { audioUrlForCandidate, useReview } from './useReview'
import { useShownCandidates } from './useShownCandidates'
import { useSwipe } from './useSwipe'
import { listItems, sectionToggleLabel, visibleCandidates, type ListItem } from './sections'
import type { CandidateSection, DecisionButton, SourceStatus } from '@/api/types'
import css from './review.module.css'

const DECISION: Partial<Record<ReviewAction, DecisionButton>> = { learn: 'learn', cloze: 'cloze', known: 'known', skip: 'skip' }
type PhoneView = 'card' | 'text' | 'list'

const SOURCES_PATH = '/'
/** Источник разобран (статус выводит backend): остальное — по желанию. */
const DONE = 'Done'
const REVIEWED: SourceStatus = 'reviewed'
/** Ссылка на конкретную карточку: с ней ревью открывается сразу на ней. */
const CANDIDATE_PARAM = 'candidate'

export function ReviewScreen() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const sourcesPath = backIn(useLocation().state, SOURCES_PATH)
  const [searchParams] = useSearchParams()
  const requestedCandidate = searchParams.get(CANDIDATE_PARAM)
  const review = useReview(Number(id), requestedCandidate === null ? null : Number(requestedCandidate))
  const listRef = useRef<HTMLDivElement>(null)
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

  const { source, candidates, currentId, counts, editing } = review
  // На телефоне карточка занимает экран, а текст источника и список открываются на её месте.
  const [phoneView, setPhoneView] = useState<PhoneView>('card')
  const togglePhoneView = (view: PhoneView) => setPhoneView(prev => (prev === view ? 'card' : view))
  const current = candidates.find(c => c.phrase_id === currentId) ?? null
  // Разделы есть во всех сортировках, кроме порядка текста; разделы под Ready, Reviewed последним, свёрнуты, пока их не открыли.
  const sectioned = review.sortOrder !== 'chronological'
  const [openedSections, setOpenedSections] = useState<ReadonlySet<CandidateSection>>(new Set())
  // Карточка, открытая ссылкой или кликом по тексту, видна, даже если её раздел свёрнут.
  const openSections = current?.section ? new Set([...openedSections, current.section]) : openedSections
  const toggleSection = (section: CandidateSection) => setOpenedSections(prev => {
    const next = new Set(prev)
    if (openSections.has(section)) next.delete(section)
    else next.add(section)
    return next
  })
  const visible = sectioned ? visibleCandidates(candidates, openSections) : candidates
  const list = useShownCandidates(
    visible,
    source?.initially_shown_candidates ?? null,
    currentId,
    `${id}:${review.sortOrder}`,
  )

  // Держим карточку в поле зрения: и когда список только появился (ревью открыли ссылкой на карточку),
  // и когда фоновое обновление переставило её в списке.
  const currentIndex = visible.findIndex(c => c.phrase_id === currentId)
  const prevId = visible[currentIndex - 1]?.phrase_id ?? null
  const nextId = currentIndex >= 0 ? visible[currentIndex + 1]?.phrase_id ?? null : null
  // На телефоне фразы листают свайпом по карточке: влево — следующая, вправо — предыдущая.
  const swipe = useSwipe(direction => {
    const target = direction === 'left' ? nextId : prevId
    if (target !== null) review.setCurrentId(target)
  })
  const { loading } = review
  useEffect(() => {
    if (loading) return
    listRef.current?.querySelector(`[data-candidate-id="${currentId}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [currentId, currentIndex, loading, phraseListShown])

  const { press, setCurrentId, cancelEditing, sourceId, clozeEditing } = review
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
      const button = current.state.buttons.find(b => b.button === DECISION[action])
      if (button) void press(current.phrase_id, button)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [current, prevId, nextId, editing, selection, press, setCurrentId, cancelEditing, toggleAudio, sourceId, clozeEditing])

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
  if (!source) {
    return <Page immersive header={<PageHeader title="Review" back={sourcesPath} />}><Empty>Source not found.</Empty></Page>
  }

  const closeSelection = () => {
    setSelection(null)
    window.getSelection()?.removeAllRanges()
  }

  const hasSourceText = source.has_source_text

  // Правка границ фразы идёт по тексту источника — на телефоне показываем его.
  const view: PhoneView = editing ? 'text' : phoneView

  const showCard = (id: number) => {
    setCurrentId(id)
    setPhoneView('card')
  }

  const items: ListItem[] = sectioned
    ? listItems(candidates, list.shown, openSections)
    : list.shown.map(candidate => ({ kind: 'candidate', candidate }))
  const sectionToggle = (section: CandidateSection, count: number, open: boolean) => (
    <div key={section} className={css.sectionToggle}>
      <Button variant="link" onClick={() => toggleSection(section)}>{sectionToggleLabel(section, count, open)}</Button>
    </div>
  )

  const goToExport = () => navigate(`/sources/${sourceId}/export`)
  // На телефоне всё редкое — в одном меню, чтобы шапка уместилась в строку.
  const phoneMenu: MenuItem[] = [
    { label: 'Export to Anki', icon: Upload, value: `${counts.learn}`, onSelect: goToExport },
    ...(hasSourceText ? [{ label: view === 'text' ? 'Hide source text' : 'Source text', icon: FileText, separated: true, onSelect: () => togglePhoneView('text') }] : []),
    { label: 'Sort', icon: ArrowDownWideNarrow, value: sortLabel(review.sortOrder), separated: !hasSourceText, items: sortItems(review.sortOrder, review.setSortOrder) },
    { label: 'Generate', icon: Sparkles, items: generationItems(review) },
  ]

  const header = (
    <PageHeader
      title={source.title}
      back={sourcesPath}
      metaWithActions
      meta={counts.total > 0 && (
        <>
          {/* Десктоп: прогресс — линия по нижнему краю вкладок, на всю ширину окна; видна краем глаза. */}
          <span className={css.windowProgress} style={{ '--p': `${Math.round(counts.progress * 100)}%` } as CSSProperties} />
          {source.status === REVIEWED ? DONE : `${counts.reviewed} / ${counts.total}`}
        </>
      )}
    >
      <div className={`${css.headerTools} ${css.desktopOnly}`}>
        {currentIndex >= 0 && (
          <div className={css.stepper}>
            <span className={css.position}>{currentIndex + 1} / {visible.length}</span>
            <IconButton icon={ChevronLeft} label="Previous phrase" disabled={prevId === null} onClick={() => prevId !== null && showCard(prevId)} />
            <IconButton icon={ChevronRight} label="Next phrase" disabled={nextId === null} onClick={() => nextId !== null && showCard(nextId)} />
          </div>
        )}
        {candidates.length > 0 && (
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
      {candidates.length > 0 && (
        <div className={`${css.headerTools} ${css.phoneOnly}`}>
          <IconButton icon={List} label="All phrases" active={view === 'list'} onClick={() => togglePhoneView('list')} />
          <Menu items={phoneMenu} trigger={<IconButton icon={Ellipsis} label="More" />} />
        </div>
      )}
      {counts.total > 0 && <div className={css.phoneProgress}><Progress value={counts.progress} /></div>}
    </PageHeader>
  )

  const banner = (
    <>
      {review.vpnBlocked && <Banner tone="warn" onDismiss={review.dismissVpn}>AI unavailable — turn on VPN</Banner>}
      {editing && <Banner tone="warn" onDismiss={cancelEditing}>Select the new boundary for “{editing.lemma}” in the source text</Banner>}
    </>
  )

  const sourceText = (onWordClick: (id: number) => void) => review.document && (
    <SourceText
      document={review.document}
      candidates={candidates}
      focusId={editing?.candidateId ?? currentId}
      onWordClick={onWordClick}
      onTextSelected={(selected, point) => setSelection({ selected, point })}
    />
  )

  const aside = hasSourceText && (
    <Aside>{sourceText(setCurrentId)}</Aside>
  )

  return (
    <Page fit wide immersive header={header} aside={aside || undefined} asideHidden={!sourceTextShown} banner={(review.vpnBlocked || editing) ? banner : undefined}>
      <div ref={listRef} className={phraseListShown ? css.body : `${css.body} ${css.focus}`}>
        {candidates.length === 0 && <Empty>No candidates found for this source.</Empty>}
        {view === 'text' && hasSourceText && <div className={css.textPanel}>{sourceText(showCard)}</div>}
        {view === 'list' && (
          <div className={css.listPanel}>
            {items.map(item => item.kind === 'section'
              ? sectionToggle(item.section, item.count, item.open)
              : <PhraseRow key={item.candidate.phrase_id} candidate={item.candidate} current={item.candidate.phrase_id === currentId} onSelect={showCard} />)}
            {list.hiddenCount > 0 && (
              <Button variant="link" onClick={list.showMore}>Show {list.nextPageCount} more · {list.hiddenCount} left</Button>
            )}
          </div>
        )}
        <div className={view === 'card' ? css.queue : `${css.queue} ${css.away}`} {...swipe}>
          {items.map(item => {
            if (item.kind === 'section') return sectionToggle(item.section, item.count, item.open)
            const { candidate } = item
            return candidate.phrase_id === currentId
              ? <PhraseCard key={candidate.phrase_id} candidate={candidate} review={review} />
              : <PhraseRow key={candidate.phrase_id} candidate={candidate} onSelect={setCurrentId} />
          })}
        </div>
        {list.hiddenCount > 0 && (
          <div className={css.showMore}>
            <Button variant="link" onClick={list.showMore}>
              Show {list.nextPageCount} more · {list.hiddenCount} left
            </Button>
          </div>
        )}
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
          onAddWord={async targetWords => { if (await review.addWord(targetWords, selection.selected.selection)) setSelection(null) }}
          onCancel={closeSelection}
        />
      )}
      <Toast message={review.toast} />
    </Page>
  )
}
