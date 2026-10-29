import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import type { BootstrapWord, CalibrationOrder } from '@/api/types'
import { Aside, Page, PageHeader } from '@/shell'
import { Button, Chip, DividerRow, Empty, Segmented, Spinner, Stack } from '@/ui'
import css from './calibrate.module.css'

const SETTINGS_PATH = '/settings'
const ORDERS: { value: CalibrationOrder; label: string }[] = [
  { value: 'review', label: 'Like Review' },
  { value: 'spread', label: 'Mixed' },
]

export function CalibrateScreen() {
  const navigate = useNavigate()
  const [words, setWords] = useState<BootstrapWord[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [round, setRound] = useState(1)
  const [checkedCount, setCheckedCount] = useState(0)
  const [order, setOrder] = useState<CalibrationOrder>('review')

  const fetchWords = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getBootstrapWords(order)
      setWords(data)
      setSelected(new Set())
    } finally {
      setLoading(false)
    }
  }, [order])

  useEffect(() => {
    void fetchWords()
  }, [fetchWords])

  const toggleWord = (lemma: string) => setSelected(prev => {
    const next = new Set(prev)
    if (next.has(lemma)) next.delete(lemma)
    else next.add(lemma)
    return next
  })

  const saveAndContinue = async (finish: boolean) => {
    setSaving(true)
    try {
      await api.saveCalibrationRound(words.map(word => word.lemma), [...selected])
      setCheckedCount(count => count + words.length)
      if (finish) {
        navigate(SETTINGS_PATH)
      } else {
        setRound(current => current + 1)
        await fetchWords()
      }
    } finally {
      setSaving(false)
    }
  }

  const aside = (
    <Aside title="This session">
      <DividerRow compact label="Round"><b>{round}</b></DividerRow>
      <DividerRow compact last label="Words checked"><b>{checkedCount}</b></DividerRow>
    </Aside>
  )

  const header = (
    <PageHeader title="Vocabulary calibration" back={SETTINGS_PATH}>
      <Segmented value={order} options={ORDERS} onChange={setOrder} />
    </PageHeader>
  )

  return (
    <Page header={header} aside={aside}>
      {loading ? <Empty><Spinner /></Empty> : (
        <div className={css.content}>
          {words.length === 0 ? (
            <Stack gap="l">
              <span>All words reviewed.</span>
              <div><Button onClick={() => navigate(SETTINGS_PATH)}>Finish</Button></div>
            </Stack>
          ) : (
            <Stack gap="l">
              <div>
                <h2 className={css.title}>Tap the words you already know</h2>
                <div className={css.hint}>Then press Next to continue</div>
              </div>
              <Stack row wrap>
                {words.map(word => (
                  <Chip key={word.lemma} large on={selected.has(word.lemma)} onClick={() => toggleWord(word.lemma)}>{word.lemma}</Chip>
                ))}
              </Stack>
              <Stack row gap="m">
                <Button variant="fill" busy={saving} onClick={() => void saveAndContinue(false)}>Next {words.length} words</Button>
                <Button variant="link" disabled={saving} onClick={() => void saveAndContinue(true)}>Finish</Button>
              </Stack>
            </Stack>
          )}
        </div>
      )}
    </Page>
  )
}
