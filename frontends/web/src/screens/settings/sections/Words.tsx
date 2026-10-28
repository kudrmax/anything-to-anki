import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GripVertical } from 'lucide-react'
import type { FrequentWordThresholdOption } from '@/api/types'
import { Button, DividerRow, Icon, Modal, Segmented, Select, Spinner, Text } from '@/ui'
import css from '../settings.module.css'
import { Group } from './Group'
import { MyWords, type WordListKind } from './MyWords'
import type { SectionProps } from './types'

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => ({ value: level, label: level }))
const frequentWordThresholdLabel = ({ value, examples }: FrequentWordThresholdOption) =>
  examples.length > 0 ? `${value} — ${examples.join(', ')}` : 'Off'
const USAGE_GROUP_LABELS: Record<string, string> = {
  neutral: 'Standard, unmarked words',
  informal: 'Slang, casual speech',
  formal: 'Formal register',
  specialized: 'Technical, domain-specific',
  connotation: 'Disapproving, approving, humorous',
  'old-fashioned': 'Dated, archaic',
  offensive: 'Offensive language',
  other: 'Literary, trademark, etc.',
}

interface WordsProps extends SectionProps {
  list: WordListKind
  onList: (list: WordListKind) => void
}

export function Words({ store, form, list, onList }: WordsProps) {
  return (
    <>
      <Group>
        <DividerRow label="Your level" hint="The CEFR level you are learning now. Words of this level and harder are suggested; easier ones count as known.">
          <Segmented value={form.cefr_level} options={CEFR_LEVELS} onChange={level => store.change('cefr_level', level)} />
        </DividerRow>
        <DividerRow
          label="Frequent words"
          hint="Words at least this common go to the bottom of the list as probably known. Each option shows examples; a lower value moves more words down."
        >
          <Select value={form.frequent_word_threshold} onChange={e => store.change('frequent_word_threshold', e.target.value)}>
            {store.frequentWordThresholds.map(option => (
              <option key={option.value} value={option.value}>{frequentWordThresholdLabel(option)}</option>
            ))}
          </Select>
        </DividerRow>
        <Calibration store={store} form={form} />
      </Group>
      <UsagePriority store={store} form={form} />
      <Group title="Your words">
        <MyWords store={store} list={list} onList={onList} />
      </Group>
      <AnalysisConfirm store={store} />
    </>
  )
}

/** Смена уровня или частотности заново анализирует все источники: только с согласия. */
function AnalysisConfirm({ store }: { store: SectionProps['store'] }) {
  const { confirming } = store
  if (!confirming) return null
  const option = store.frequentWordThresholds.find(o => o.value === confirming.value)
  const title = confirming.key === 'cefr_level' ? `Change your level to ${String(confirming.value)}?`
    : option ? `Set frequent words to ${frequentWordThresholdLabel(option)}?`
      : 'Apply the new value?'
  return (
    <Modal
      title={title}
      onClose={store.cancelChange}
      footer={
        <>
          <Button variant="link" onClick={store.cancelChange}>Cancel</Button>
          <Button variant="fill" onClick={store.confirmChange}>Analyse again</Button>
        </>
      }
    >
      <Text tone="soft">Every source is analysed again with the new value. It takes a while; the progress is shown on screen.</Text>
    </Modal>
  )
}

function Calibration({ store }: SectionProps) {
  const navigate = useNavigate()
  const bootstrap = store.bootstrapStatus
  return (
    <DividerRow
      last
      label="Calibration"
      hint={
        bootstrap?.status === 'ready' ? `Ready — ${bootstrap.word_count} words, built ${bootstrap.built_at ? new Date(bootstrap.built_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}`
          : bootstrap?.status === 'error' ? <Text tone="err">{bootstrap.error ?? 'Build failed'}</Text>
            : bootstrap?.status === 'building' ? 'Building word list…'
              : 'Mark the words you already know on a ready list.'
      }
    >
      {bootstrap?.status === 'building' && <Spinner />}
      {bootstrap?.status === 'none' && <Button onClick={() => void store.buildBootstrap()}>Prepare</Button>}
      {bootstrap?.status === 'error' && <Button onClick={() => void store.buildBootstrap()}>Retry</Button>}
      {bootstrap?.status === 'ready' && (
        <div className={css.actions}>
          <Button variant="link" onClick={() => void store.buildBootstrap()}>Rebuild</Button>
          <Button onClick={() => navigate('/calibrate')}>Calibrate</Button>
        </div>
      )}
    </DividerRow>
  )
}

function UsagePriority({ store, form }: SectionProps) {
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dropIndex, setDropIndex] = useState<number | null>(null)
  const dragCounter = useRef(0)
  const order = form.usage_group_order ?? Object.keys(USAGE_GROUP_LABELS)

  const drop = (fromIndex: number, toIndex: number) => {
    if (Number.isNaN(fromIndex) || fromIndex === toIndex) return
    const next = [...order]
    const [moved] = next.splice(fromIndex, 1)
    next.splice(toIndex, 0, moved)
    store.change('usage_group_order', next)
  }

  return (
    <Group collapsible title="Usage priority" hint="Words from groups higher up are suggested first. Drag to reorder.">
      {order.map((group, index) => (
        <DividerRow
          key={group}
          compact
          last={index === order.length - 1}
          lead={<Icon as={GripVertical} size="s" />}
          label={
            <span className={css.named}>
              <span className={css.name}>{group}</span>
              <Text tone="muted" size="s">{USAGE_GROUP_LABELS[group]}</Text>
            </span>
          }
          state={dragIndex === index ? 'dragging' : dropIndex === index ? 'target' : undefined}
          draggable
          onDragStart={e => { setDragIndex(index); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(index)) }}
          onDragEnd={() => { setDragIndex(null); setDropIndex(null); dragCounter.current = 0 }}
          onDragEnter={() => { dragCounter.current++; setDropIndex(index) }}
          onDragLeave={() => { dragCounter.current--; if (dragCounter.current <= 0) { setDropIndex(null); dragCounter.current = 0 } }}
          onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }}
          onDrop={e => {
            e.preventDefault()
            dragCounter.current = 0
            setDropIndex(null)
            drop(parseInt(e.dataTransfer.getData('text/plain'), 10), index)
          }}
        />
      ))}
    </Group>
  )
}
