// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Upload } from 'lucide-react'
import type { CandidateSection } from '@/api/types'
import { Aside, Page, PageHeader } from '@/shell'
import { Button, Empty, Icon, Progress, Text } from '@/ui'
import { sectionToggleLabel } from '@/screens/review/sections'
import css from '@/screens/review/review.module.css'
import { AddPartModal } from './AddPartModal'
import { WHOLE, type Card, type CardStatus, type Source } from './mockData'
import { cardsIn, occurrences, readyProgress, scopeLabel, sentenceIndex, takeLabel, wordsLeft } from './model'
import { PartText } from './PartText'
import { PrototypeCard, PrototypeRow } from './PrototypeCard'
import { PrototypeGenerateMenu } from './PrototypeGenerateMenu'
import { PROTOTYPE_PATH, usePrototype } from './prototypeContext'
import { PartPicker, TakeButton } from './TakeControls'
import local from './prototype.module.css'

const FOLDED: CandidateSection[] = ['extra', 'probably_known']
const DECISION_KEYS: Record<string, CardStatus> = { '1': 'learn', '3': 'known', '4': 'skip' }

export function PrototypeReviewScreen() {
  const { id } = useParams<{ id: string }>()
  const source = usePrototype().sources.find(s => s.id === id)
  if (!source) {
    return <Page header={<PageHeader title="Review" back={PROTOTYPE_PATH} />}><Empty>Source not found.</Empty></Page>
  }
  return <ReviewBody key={source.id} source={source} />
}

const typing = (target: EventTarget | null): boolean =>
  target instanceof HTMLElement && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)

function ReviewBody({ source }: { source: Source }) {
  const proto = usePrototype()
  const { scope, order, count } = proto.prefsOf(source.id)
  const [pickedId, setPickedId] = useState<string | null>(null)
  const [opened, setOpened] = useState<ReadonlySet<CandidateSection>>(new Set())
  const [adding, setAdding] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  const sentences = useMemo(() => sentenceIndex(source), [source])
  const cards = cardsIn(source, scope)
  const whole = scope === WHOLE
  const partOf = (partId: string) => source.parts.find(p => p.id === partId)
  const labelOfPart = (partId: string) => partOf(partId)?.label ?? ''

  const bySection = (section: CandidateSection) => cards.filter(c => c.section === section)
  const visibleWith = (open: ReadonlySet<CandidateSection>) =>
    [...bySection('ready'), ...FOLDED.flatMap(section => (open.has(section) ? bySection(section) : []))]
  const firstVisible = visibleWith(opened)
  const current = cards.find(c => c.id === pickedId) ?? firstVisible.find(c => c.status === 'pending') ?? firstVisible[0] ?? null
  // A card picked in the text stays visible even if its section is folded.
  const open = current ? new Set([...opened, current.section]) : opened
  const visible = visibleWith(open)
  const currentIndex = current ? visible.findIndex(c => c.id === current.id) : -1

  const decide = (card: Card, status: CardStatus) => {
    proto.decide(source.id, card.id, status)
    if (card.status !== 'pending') return
    const index = visible.findIndex(c => c.id === card.id)
    const next = visible.slice(index + 1).find(c => c.status === 'pending')
    setPickedId(next?.id ?? card.id)
  }

  const currentCardId = current?.id ?? null
  useEffect(() => {
    if (currentCardId === null) return
    listRef.current?.querySelector(`[data-card-id="${currentCardId}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [currentCardId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (adding || typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const target = visible[currentIndex + (e.key === 'ArrowDown' ? 1 : -1)]
        if (target) { e.preventDefault(); setPickedId(target.id) }
        return
      }
      const status = DECISION_KEYS[e.key]
      if (status && current) { e.preventDefault(); decide(current, status) }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  })

  const label = scopeLabel(source, scope)
  const multiPart = source.parts.length > 1
  const left = wordsLeft(source, scope)
  const progress = readyProgress(cards)
  const busy = proto.rebuilding(source.id)
  const take = () => proto.take(source.id, scope, count, order)
  const changeScope = (next: string) => { proto.setScope(source.id, next); setPickedId(null) }
  const fresh = multiPart && source.cards.length === 0

  const picker = multiPart && (
    <PartPicker source={source} scope={scope} label={label} onChange={changeScope} onAddPart={() => setAdding(true)} />
  )
  const takeButton = left === 0
    ? <Text tone="muted" size="s">All words from {label} are taken</Text>
    : (
        <TakeButton
          from={multiPart ? label : ''}
          left={left}
          count={count}
          order={order}
          busy={busy}
          onTake={take}
          onCount={n => proto.setCount(source.id, n)}
          onOrder={o => proto.setOrder(source.id, o)}
        />
      )

  const done = cards.filter(c => sentences.get(c.sentenceId)?.polished).length
  const header = (
    <PageHeader
      title={source.title}
      back={PROTOTYPE_PATH}
      metaWithActions
      meta={
        <>
          {!fresh && picker}
          {progress.total > 0 && (
            <>
              <Progress inline value={progress.decided / progress.total} />
              {progress.decided}/{progress.total}
            </>
          )}
        </>
      }
    >
      <div className={css.headerTools}>
        {cards.length > 0 && (
          <PrototypeGenerateMenu
            done={done}
            total={cards.length}
            running={proto.running(source.id)}
            onRun={(kind, mode) => proto.generate(source.id, kind, mode)}
            onCancel={kind => proto.cancel(source.id, kind)}
          />
        )}
      </div>
      <Button variant="fill" title="Export cards to Anki (not part of the prototype)">
        <Icon as={Upload} size="s" />{cards.filter(c => c.status === 'learn').length}
      </Button>
    </PageHeader>
  )

  const textPart = whole ? (current && partOf(current.partId)) ?? source.parts[0] : partOf(scope) ?? source.parts[0]
  const aside = (
    <Aside>
      <PartText
        part={textPart}
        label={whole ? `${textPart.label} · ${textPart.title}` : null}
        cards={source.cards}
        currentId={current?.id ?? null}
        onSelect={cardId => setPickedId(cardId)}
      />
    </Aside>
  )

  const toggle = (section: CandidateSection) => setOpened(prev => {
    const next = new Set(prev)
    if (open.has(section)) next.delete(section)
    else next.add(section)
    return next
  })
  const row = (card: Card) => {
    const sentence = sentences.get(card.sentenceId)
    if (!sentence) return null
    const partLabel = whole ? labelOfPart(card.partId) : null
    if (card.id === current?.id) {
      return (
        <PrototypeCard
          key={card.id}
          card={card}
          sentence={sentence}
          partLabel={partLabel}
          others={occurrences(source, scope, card.lemma).filter(s => s.id !== sentence.id)}
          labelOfPart={labelOfPart}
          onDecide={status => decide(card, status)}
          onChoosePhrase={sentenceId => proto.choosePhrase(source.id, card.id, sentenceId)}
        />
      )
    }
    return <PrototypeRow key={card.id} card={card} sentence={sentence} partLabel={partLabel} onSelect={() => setPickedId(card.id)} />
  }

  const list = (
    <div className={css.queue}>
      {bySection('ready').map(row)}
      {FOLDED.map(section => {
        const sectionCards = bySection(section)
        if (sectionCards.length === 0) return null
        const isOpen = open.has(section)
        return [
          <div key={section} className={css.sectionToggle}>
            <Button variant="link" onClick={() => toggle(section)}>{sectionToggleLabel(section, sectionCards.length, isOpen)}</Button>
          </div>,
          ...(isOpen ? sectionCards.map(row) : []),
        ]
      })}
    </div>
  )

  const body = (() => {
    if (fresh) {
      return (
        <div className={local.start}>
          <div className={local.startTitle}>Where do you want words from?</div>
          <div className={local.startRow}>
            {picker}
            <Button variant="fill" busy={busy} onClick={take}>
              {busy ? 'Rebuilding…' : `Take ${count === 'all' || count >= left ? `all ${left}` : count}`}
            </Button>
          </div>
          <Text tone="muted" size="s">{takeLabel(label, left, count)} · nothing is generated until you press ✨</Text>
        </div>
      )
    }
    if (cards.length === 0) {
      return (
        <Empty>
          <div className={local.emptyPart}>
            <span>No cards from {label} yet</span>
            {takeButton}
          </div>
        </Empty>
      )
    }
    return (
      <>
        {list}
        {(multiPart || left > 0) && <div className={local.takeBar}>{takeButton}</div>}
        <div className={css.hint}>↑ ↓ — next phrase · 1 Learn · 3 Know · 4 Skip</div>
      </>
    )
  })()

  return (
    <Page fit wide header={header} aside={aside}>
      <div ref={listRef} className={css.body}>{body}</div>
      {adding && (
        <AddPartModal
          source={source}
          onAdd={(title, text) => { proto.addPart(source.id, title, text); setPickedId(null) }}
          onClose={() => setAdding(false)}
        />
      )}
    </Page>
  )
}
