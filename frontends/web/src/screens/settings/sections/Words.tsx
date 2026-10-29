import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GripVertical } from 'lucide-react'
import type { FrequentWordThresholdOption } from '@/api/types'
import { Button, DividerRow, Icon, Modal, Segmented, Spinner, Text } from '@/ui'
import css from '../settings.module.css'
import { Group } from './Group'
import { MyWords, type WordListKind } from './MyWords'
import type { SectionProps } from './types'

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => ({ value: level, label: level }))
const USAGE_GROUPS: Record<string, { name: string; description: string }> = {
  neutral: { name: 'Neutral', description: 'Standard, unmarked words' },
  informal: { name: 'Informal', description: 'Slang, casual speech' },
  formal: { name: 'Formal', description: 'Formal register' },
  specialized: { name: 'Specialized', description: 'Technical, domain-specific' },
  connotation: { name: 'Connotation', description: 'Disapproving, approving, humorous' },
  'old-fashioned': { name: 'Old-fashioned', description: 'Dated, archaic' },
  offensive: { name: 'Offensive', description: 'Offensive language' },
  other: { name: 'Other', description: 'Literary, trademark, etc.' },
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
        <Calibration store={store} form={form} />
        <SkippedInCalibration store={store} form={form} />
      </Group>
      <FrequentWords store={store} form={form} />
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
  return (
    <Modal
      title={confirming.key === 'cefr_level' ? `Change your level to ${String(confirming.value)}?` : 'Change frequent words?'}
      onClose={store.cancelChange}
      footer={
        <>
          <Button variant="link" onClick={store.cancelChange}>Cancel</Button>
          <Button variant="fill" onClick={store.confirmChange}>Analyse again</Button>
        </>
      }
    >
      {option && option.examples.length > 0 && (
        <div className={css.confirmChoice}>
          <Text tone="soft">Words as common as these, or more common, go to the bottom of the list:</Text>
          <ThresholdChoice option={option} />
        </div>
      )}
      {option && option.examples.length === 0 && (
        <div className={css.confirmChoice}><Text tone="soft">Frequent words stay in place in the list.</Text></div>
      )}
      <Text tone="soft">Every source is analysed again with the new value. It takes a while; the progress is shown on screen.</Text>
    </Modal>
  )
}

/** Порог частотности: варианты от «вниз уходит больше всего» до «ничего», каждый показан словами-примерами. */
export function FrequentWords({ store, form }: SectionProps) {
  return (
    <Group title="Frequent words" hint="Words as common as the examples, or more common, go to the bottom of the list as probably known.">
      <div role="radiogroup" aria-label="Frequent words">
        {store.frequentWordThresholds.map(option => (
          <label key={option.value} className={css.choice}>
            <input
              type="radio"
              name="frequent_word_threshold"
              className={css.radio}
              checked={form.frequent_word_threshold === option.value}
              onChange={() => store.change('frequent_word_threshold', option.value)}
            />
            <ThresholdChoice option={option} />
          </label>
        ))}
      </div>
    </Group>
  )
}

function ThresholdChoice({ option }: { option: FrequentWordThresholdOption }) {
  if (option.examples.length === 0) {
    return (
      <span className={css.offChoice}>
        Off
        <Text tone="muted" size="s">Frequent words stay in place</Text>
      </span>
    )
  }
  return (
    <span className={css.tags}>
      {option.examples.map(word => <span key={word} className={css.tag}>{word}</span>)}
    </span>
  )
}

function Calibration({ store }: SectionProps) {
  const navigate = useNavigate()
  const bootstrap = store.bootstrapStatus
  return (
    <DividerRow
      last={store.calibrationSkipped === 0}
      label="Vocabulary calibration"
      hint={
        bootstrap?.status === 'ready' ? `Mark the words you already know on a list of ${bootstrap.word_count.toLocaleString()} words${bootstrap.built_at ? `, built ${new Date(bootstrap.built_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}.`
          : bootstrap?.status === 'error' ? <Text tone="err">{bootstrap.error ?? 'Build failed'}</Text>
            : bootstrap?.status === 'building' ? 'Building the word list…'
              : 'Mark the words you already know on a ready list. First the app builds the list.'
      }
    >
      {bootstrap?.status === 'building' && <Spinner />}
      {bootstrap?.status === 'none' && <Button onClick={() => void store.buildBootstrap()}>Build word list</Button>}
      {bootstrap?.status === 'error' && <Button onClick={() => void store.buildBootstrap()}>Retry</Button>}
      {bootstrap?.status === 'ready' && (
        <div className={css.actions}>
          <Button variant="link" onClick={() => void store.buildBootstrap()}>Rebuild list</Button>
          <Button onClick={() => navigate('/calibrate')}>Calibrate</Button>
        </div>
      )}
    </DividerRow>
  )
}

/** Слова, которые калибровка показала и которые не нажали: она их больше не спрашивает, пока их не забыть. */
function SkippedInCalibration({ store }: SectionProps) {
  const [confirming, setConfirming] = useState(false)
  const count = store.calibrationSkipped
  if (count === 0) return null
  const words = `${count.toLocaleString()} ${count === 1 ? 'word' : 'words'}`
  const forget = () => {
    setConfirming(false)
    void store.forgetCalibrationSkipped()
  }
  return (
    <DividerRow last label="Skipped in calibration" hint={`${words} you didn't tap. Calibration doesn't ask about them again.`}>
      <Button variant="link" onClick={() => setConfirming(true)}>Ask skipped words again</Button>
      {confirming && (
        <Modal
          title="Ask skipped words again?"
          onClose={() => setConfirming(false)}
          footer={
            <>
              <Button variant="link" onClick={() => setConfirming(false)}>Cancel</Button>
              <Button variant="fill" onClick={forget}>Ask again</Button>
            </>
          }
        >
          <Text tone="soft">Calibration will show the {words} you didn't tap again. Words you marked as known stay known.</Text>
        </Modal>
      )}
    </DividerRow>
  )
}

function UsagePriority({ store, form }: SectionProps) {
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dropIndex, setDropIndex] = useState<number | null>(null)
  const dragCounter = useRef(0)
  const order = form.usage_group_order ?? Object.keys(USAGE_GROUPS)

  const drop = (fromIndex: number, toIndex: number) => {
    if (Number.isNaN(fromIndex) || fromIndex === toIndex) return
    const next = [...order]
    const [moved] = next.splice(fromIndex, 1)
    next.splice(toIndex, 0, moved)
    store.change('usage_group_order', next)
  }

  return (
    <Group collapsible title="Word usage priority" hint="Words of the usage groups higher up are suggested first. Drag to reorder.">
      {order.map((group, index) => (
        <DividerRow
          key={group}
          compact
          last={index === order.length - 1}
          lead={<Icon as={GripVertical} size="s" />}
          label={
            <span className={css.named}>
              <span className={css.name}>{USAGE_GROUPS[group]?.name ?? group}</span>
              <Text tone="muted" size="s">{USAGE_GROUPS[group]?.description}</Text>
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
