import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GripVertical } from 'lucide-react'
import type { FrequentWordThresholdOption } from '@/api/types'
import { Button, DividerRow, Icon, Segmented, Select, Spinner, Text } from '@/ui'
import css from '../settings.module.css'
import { Group } from './Group'
import type { SectionProps } from './types'

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => ({ value: level, label: level }))
const AUTO_THRESHOLD = 'auto'
const frequentWordThresholdLabel = ({ value, zipf, examples }: FrequentWordThresholdOption) => {
  if (value === AUTO_THRESHOLD) return `Auto — now ${zipf === null ? 'off' : zipf.toFixed(1)}`
  return examples.length > 0 ? `${value} — ${examples.join(', ')}` : 'Off'
}
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

export function Vocabulary({ store, form }: SectionProps) {
  return (
    <>
      <Group title="Word selection">
        <DividerRow label="Your CEFR level" hint="The level you are learning now. Words of this level and harder are suggested; easier words count as known. A1 — you are just starting.">
          <Segmented value={form.cefr_level} options={CEFR_LEVELS} onChange={level => store.setField('cefr_level', level)} />
        </DividerRow>
        <DividerRow
          label="Frequent words"
          hint="Words at least this frequent go to the bottom of the list as probably known. Auto starts from your level and learns from your Know / Learn marks. Other options show examples of words that go down; lower value — more words go down."
        >
          <Select value={form.frequent_word_threshold} onChange={e => store.setField('frequent_word_threshold', e.target.value)}>
            {store.frequentWordThresholds.map(option => (
              <option key={option.value} value={option.value}>{frequentWordThresholdLabel(option)}</option>
            ))}
          </Select>
        </DividerRow>
        <Calibration store={store} form={form} />
      </Group>
      <UsagePriority store={store} form={form} />
    </>
  )
}

function Calibration({ store }: SectionProps) {
  const navigate = useNavigate()
  const bootstrap = store.bootstrapStatus
  return (
    <DividerRow
      last
      label="Vocabulary calibration"
      hint={
        bootstrap?.status === 'ready' ? `Ready — ${bootstrap.word_count} words, built ${bootstrap.built_at ? new Date(bootstrap.built_at).toLocaleDateString() : '—'}`
          : bootstrap?.status === 'error' ? <Text tone="err">{bootstrap.error ?? 'Build failed'}</Text>
            : bootstrap?.status === 'building' ? 'Building word list…'
              : 'Build a word list to calibrate what you already know.'
      }
    >
      {bootstrap?.status === 'building' && <Spinner />}
      {bootstrap?.status === 'none' && <Button onClick={() => void store.buildBootstrap()}>Prepare</Button>}
      {bootstrap?.status === 'error' && <Button onClick={() => void store.buildBootstrap()}>Retry</Button>}
      {bootstrap?.status === 'ready' && (
        <>
          <Button variant="link" onClick={() => void store.buildBootstrap()}>Rebuild</Button>
          <Button onClick={() => navigate('/calibrate')}>Calibrate</Button>
        </>
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
    store.reorderUsageGroups(next)
  }

  return (
    <Group title="Usage priority" hint="Order of usage groups in Review. Drag to reorder.">
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
