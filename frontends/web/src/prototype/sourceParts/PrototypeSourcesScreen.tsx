// Prototype for docs/specs/source-parts.md — mock data, not wired to the backend.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, Clapperboard, Ellipsis, FileText, Music, Plus, RefreshCw, type LucideIcon } from 'lucide-react'
import { Page, PageHeader } from '@/shell'
import { Button, Icon, IconButton, Menu, Modal, Progress, Text } from '@/ui'
import sources from '@/screens/sources/sources.module.css'
import { AddPartModal } from './AddPartModal'
import { WHOLE, type Source, type SourceKind } from './mockData'
import { readyProgress, wordsLeft } from './model'
import { PROTOTYPE_PATH, usePrototype } from './prototypeContext'
import css from './prototype.module.css'

const KIND_ICON: Record<SourceKind, LucideIcon> = { book: BookOpen, series: Clapperboard, song: Music, text: FileText }
const KIND_LABEL: Record<SourceKind, string> = { book: 'Book', series: 'Series', song: 'Lyrics', text: 'Text' }

function caption(source: Source): string {
  const { decided, total } = readyProgress(source.cards)
  const left = wordsLeft(source, WHOLE)
  const leftText = left > 0 ? `~${left} words left` : 'all words taken'
  if (source.cards.length === 0) return `No cards yet · ${leftText}`
  return `${decided} of ${total} decided · ${leftText}`
}

function kindLine(source: Source): string {
  const parts = source.parts.length
  return parts > 1 ? `${KIND_LABEL[source.kind]} · ${parts} ${source.partNoun === 'Episode' ? 'episodes' : 'parts'}` : KIND_LABEL[source.kind]
}

type Dialog = { kind: 'add' | 'rebuild'; source: Source } | null

export function PrototypeSourcesScreen() {
  const proto = usePrototype()
  const navigate = useNavigate()
  const [dialog, setDialog] = useState<Dialog>(null)
  const open = (source: Source) => navigate(`${PROTOTYPE_PATH}/${source.id}`)

  return (
    <Page header={<PageHeader title="Sources" meta="Prototype: source parts" />}>
      <section className={sources.group}>
        <h2 className={sources.groupTitle}>In progress<span>{proto.sources.length}</span></h2>
        {proto.sources.map(source => {
          const { decided, total } = readyProgress(source.cards)
          const reviewed = total > 0 && decided === total && wordsLeft(source, WHOLE) === 0
          return (
            <div key={source.id} className={`${sources.row} ${sources.clickable}${reviewed ? ` ${sources.done}` : ''}`} onClick={() => open(source)}>
              <span className={sources.type}><Icon as={KIND_ICON[source.kind]} /></span>
              <div className={sources.name}>
                <span className={sources.title}>{source.title}</span>
                <span className={sources.path}>{kindLine(source)}</span>
              </div>
              <div className={sources.progress}>
                <Progress value={total > 0 ? decided / total : 0} />
                <Text tone="muted" size="s">{caption(source)}</Text>
              </div>
              <div className={sources.action} onClick={e => e.stopPropagation()}>
                <Button variant={reviewed ? 'link' : 'soft'} onClick={() => open(source)}>
                  {source.cards.length === 0 ? 'Review' : reviewed ? 'Open' : 'Continue'}
                </Button>
              </div>
              <div className={sources.more} onClick={e => e.stopPropagation()}>
                <Menu
                  trigger={<IconButton icon={Ellipsis} label="More" />}
                  items={[
                    { label: 'Add part…', icon: Plus, onSelect: () => setDialog({ kind: 'add', source }) },
                    { label: 'Rebuild unreviewed…', icon: RefreshCw, onSelect: () => setDialog({ kind: 'rebuild', source }) },
                  ]}
                />
              </div>
            </div>
          )
        })}
      </section>
      {dialog?.kind === 'add' && (
        <AddPartModal
          source={dialog.source}
          onAdd={(title, text) => { proto.addPart(dialog.source.id, title, text); open(dialog.source) }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === 'rebuild' && <RebuildModal source={dialog.source} onClose={() => setDialog(null)} />}
    </Page>
  )
}

const CHANGED_SHARE = 3

function RebuildModal({ source, onClose }: { source: Source; onClose: () => void }) {
  const [withUndecided, setWithUndecided] = useState(false)
  const undecided = source.cards.filter(c => c.status === 'pending').length
  const changed = Math.ceil(undecided / CHANGED_SHARE)
  return (
    <Modal
      title={`Rebuild ${source.title}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="link" onClick={onClose}>Cancel</Button>
          <Button variant="fill" onClick={onClose}>Rebuild</Button>
        </>
      }
    >
      <Text tone="soft">Rebuild words not taken yet with current settings</Text>
      <div>
        <label className={css.check}>
          <input type="checkbox" checked={withUndecided} onChange={e => setWithUndecided(e.target.checked)} />
          Also cards without a decision
        </label>
        <div className={css.checkNote}>
          <Text tone="muted" size="s">{changed} of {undecided} will get a new phrase — their AI results reset</Text>
        </div>
      </div>
      <Text tone="muted" size="s">A new AI prompt is applied through ✨ → Regenerate</Text>
    </Modal>
  )
}
