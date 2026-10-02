import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { decisionChange, type Decision } from '@/lib/decision'
import { reviewAction, type ReviewAction } from '@/lib/hotkeys'
import { sourceTextShownPref } from '@/lib/preferences'
import { Aside, Page, PageHeader } from '@/shell'
import { PanelRightClose, PanelRightOpen, Upload } from 'lucide-react'
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
const SOURCES_PATH = '/'

export function ReviewScreen() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const review = useReview(Number(id))
  const listRef = useRef<HTMLDivElement>(null)
  const [selection, setSelection] = useState<{ phrase: string; point: SelectionPoint } | null>(null)
  const [sourceTextShown, setSourceTextShown] = useState(() => sourceTextShownPref.read())
  const toggleSourceText = () => {
    sourceTextShownPref.write(!sourceTextShown)
    setSourceTextShown(!sourceTextShown)
  }

  const { source, candidates, currentId, counts, editing } = review
  const current = candidates.find(c => c.id === currentId) ?? null
  const list = useShownCandidates(
    candidates,
    source?.initially_shown_candidates ?? null,
    currentId,
    `${id}:${review.sortOrder}`,
  )

  useEffect(() => {
    listRef.current?.querySelector(`[data-candidate-id="${currentId}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [currentId])

  const { mark, setCurrentId, cancelEditing, sourceId } = review
  const toggleAudio = review.player.toggle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && editing && !selection) { cancelEditing(); return }
      const action = reviewAction(e)
      if (!action) return
      e.preventDefault()
      const index = candidates.findIndex(c => c.id === currentId)
      if (action === 'prev' || action === 'next') {
        const next = candidates[index + (action === 'next' ? 1 : -1)]
        if (next) setCurrentId(next.id)
        return
      }
      if (!current) return
      if (action === 'audio') {
        const url = audioUrlForCandidate(current, sourceId)
        if (url) toggleAudio(url)
        return
      }
      const status = DECISION[action]
      if (status) void mark(current.id, decisionChange(current.status, status))
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [candidates, current, currentId, editing, selection, mark, setCurrentId, cancelEditing, toggleAudio, sourceId])

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

  // У темы нет своего текста: её фразы собраны из других источников.
  const hasSourceText = source.content_type !== 'topic'

  const header = (
    <PageHeader
      title={source.title}
      back={SOURCES_PATH}
      meta={candidates.length > 0 && (
        <>
          <Progress inline value={counts.progress} />
          {counts.marked} / {counts.total}
        </>
      )}
    >
      <div className={css.headerTools}>
        {candidates.length > 0 && (
          <>
            <SortMenu value={review.sortOrder} onChange={review.setSortOrder} />
            <GenerateMenu review={review} />
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

  const aside = hasSourceText && (
    <Aside>
      <SourceText
        text={source.cleaned_text ?? source.raw_text}
        candidates={candidates}
        focusId={editing?.candidateId ?? currentId}
        onWordClick={setCurrentId}
        onTextSelected={(phrase, point) => setSelection({ phrase, point })}
      />
    </Aside>
  )

  return (
    <Page wide header={header} aside={aside || undefined} asideHidden={!sourceTextShown} banner={(review.vpnBlocked || editing) ? banner : undefined}>
      <div ref={listRef}>
        {candidates.length === 0 && <Empty>No candidates found for this source.</Empty>}
        <div className={css.queue}>
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
          <div className={css.hint}>↑ ↓ — next phrase · 1 Learn · 2 Know · 3 Skip · Space — play audio</div>
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
