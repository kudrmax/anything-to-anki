import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { DetectedFormat, Question } from '@/api/types'
import { nativeHost } from '@/lib/nativeHost'
import { withDroppedPaths } from '@/lib/text/sourceInput'
import { pickedWords, toggled } from '@/lib/text/words'
import { Button, Field, Stack, Tabs, Text, TextArea, WordPicker } from '@/ui'
import css from './AddSourceForm.module.css'
import { PathField } from './PathField'
import { QuestionsModal } from './QuestionsModal'
import { useFileDrag } from './useFileDrag'

type Tab = 'source' | 'topic' | 'phrase'

const TABS: { value: Tab; label: string }[] = [
  { value: 'source', label: 'Source' },
  { value: 'topic', label: 'Topic' },
  { value: 'phrase', label: 'Phrase' },
]
const SOURCE_PLACEHOLDER = 'Paste text, a file path or a link…'
const TOPIC_PLACEHOLDER = 'Negotiating a salary, phrasal verbs with get…'
const TOPIC_HINT = 'Targets come from AI, phrases from your sources'
const PHRASE_PLACEHOLDER = 'Paste a phrase you came across…'
const PHRASE_HINT = 'Tap words to select target'
const PHRASE_SAVED = 'Phrase saved'
const SUBTITLE_EXTENSIONS = ['srt']
const NO_SUBTITLES_ERROR = 'subtitles_not_available'
const DROP_HINT = 'Drop the file here'
const DRAG_HINT = 'or drag a file here'
const BROWSER_DROP_ERROR = 'Dropped files reach the app only in the macOS app — enter the path instead'
const DETECT_DELAY_MS = 300

interface AddSourceFormProps {
  onReload: () => Promise<void>
  onToast: (message: string) => void
}

const messageOf = (e: unknown): string => (e instanceof Error ? e.message : String(e))

export function AddSourceForm({ onReload, onToast }: AddSourceFormProps) {
  const [tab, setTab] = useState<Tab>('source')
  const [title, setTitle] = useState('')
  const [input, setInput] = useState('')
  const [srtPath, setSrtPath] = useState('')
  const [detected, setDetected] = useState<DetectedFormat | null>(null)
  const [topic, setTopic] = useState('')
  const [phrase, setPhrase] = useState('')
  const [phraseTarget, setPhraseTarget] = useState<Set<number>>(new Set())
  const [phraseSaved, setPhraseSaved] = useState(false)
  const [adding, setAdding] = useState(false)
  const [picking, setPicking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [questions, setQuestions] = useState<Question[] | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [host] = useState(() => nativeHost())

  const fileDrag = useFileDrag({
    onEnter: () => {
      setTab('source')
      setError(null)
    },
    onBrowserDrop: () => setError(BROWSER_DROP_ERROR),
  })
  const resetFileDrag = fileDrag.reset

  useEffect(() => host?.onFileDrop(paths => {
    resetFileDrag()
    setTab('source')
    setError(null)
    const chosen = withDroppedPaths({ filePath: input, srtPath }, paths)
    setInput(chosen.filePath)
    setSrtPath(chosen.srtPath)
  }), [host, input, srtPath, resetFileDrag])

  // Подсказку под полем считает backend: как он прочитает то, что вставлено.
  useEffect(() => {
    if (!input.trim()) { setDetected(null); return }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      api.detectFormat(input, controller.signal).then(setDetected).catch(() => {})
    }, DETECT_DELAY_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [input])

  const isVideo = detected?.format === 'video_file'

  const pickFile = async () => {
    if (!host) return
    setPicking(true)
    try {
      const path = await host.pickFile()
      if (path) {
        setInput(path)
        setSrtPath('')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open the file picker')
    } finally {
      setPicking(false)
    }
  }

  const submitSource = async (given: Record<string, string>) => {
    setAdding(true)
    try {
      const result = await api.addSource(input, isVideo ? srtPath.trim() : '', title.trim(), given)
      if ('questions' in result) {
        setAnswers(given)
        setQuestions(result.questions)
        return
      }
      setInput('')
      setSrtPath('')
      setTitle('')
      setAnswers({})
      await onReload()
    } catch (e) {
      const message = messageOf(e)
      if (message.includes(NO_SUBTITLES_ERROR)) onToast('Subtitles are not available for this video')
      else setError(message)
    } finally {
      setAdding(false)
    }
  }

  const answer = (given: Record<string, string>) => {
    setQuestions(null)
    void submitSource({ ...answers, ...given })
  }

  const addTopic = async () => {
    if (!topic.trim()) { setError('Describe what you want to learn'); return }
    setAdding(true)
    try {
      await api.createTopic(topic.trim(), title.trim() || undefined)
      await onReload()
      setTopic('')
      setTitle('')
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setAdding(false)
    }
  }

  const editPhrase = (value: string) => {
    setPhrase(value)
    setPhraseTarget(new Set())
    setPhraseSaved(false)
  }

  const addPhrase = async () => {
    const target = pickedWords(phrase, phraseTarget)
    if (!phrase.trim()) { setError('Paste a phrase'); return }
    if (!target) { setError('Select target words'); return }
    setAdding(true)
    try {
      await api.addSavedPhrase(phrase.trim(), target)
      await onReload()
      editPhrase('')
      setPhraseSaved(true)
    } catch (e) {
      setError(messageOf(e))
    } finally {
      setAdding(false)
    }
  }

  const add = () => {
    setError(null)
    if (tab === 'topic') void addTopic()
    else if (tab === 'phrase') void addPhrase()
    else if (!input.trim()) setError('Paste text, a file path or a link')
    else void submitSource({})
  }

  return (
    <>
      <Tabs value={tab} options={TABS} onChange={setTab} />
      <Stack gap="m">
        <Stack>
          {tab !== 'phrase' && <Field value={title} placeholder="Title (optional)" onChange={e => setTitle(e.target.value)} />}
          {tab === 'source' && (
            <>
              {fileDrag.dragging && <div className={css.dropZone}>{DROP_HINT}</div>}
              <TextArea value={input} placeholder={SOURCE_PLACEHOLDER} onChange={e => setInput(e.target.value)} />
              {isVideo && (
                <PathField value={srtPath} placeholder="/path/to/subtitles.srt (optional)" extensions={SUBTITLE_EXTENSIONS} onChange={setSrtPath} onError={setError} />
              )}
              <div className={css.hintRow}>
                {detected
                  ? <Text tone="muted" size="s">{detected.label}</Text>
                  : host && !fileDrag.dragging && <Text tone="muted" size="s">{DRAG_HINT}</Text>}
                {host && <Button busy={picking} onClick={pickFile}>Choose…</Button>}
              </div>
            </>
          )}
          {tab === 'topic' && (
            <>
              <Field value={topic} placeholder={TOPIC_PLACEHOLDER} onChange={e => setTopic(e.target.value)} />
              <Text tone="muted" size="s">{TOPIC_HINT}</Text>
            </>
          )}
          {tab === 'phrase' && (
            <>
              <TextArea value={phrase} placeholder={PHRASE_PLACEHOLDER} onChange={e => editPhrase(e.target.value)} />
              {phrase.trim() ? (
                <>
                  <Text tone="muted" size="s">{PHRASE_HINT}</Text>
                  <WordPicker phrase={phrase} selected={phraseTarget} onToggle={i => setPhraseTarget(prev => toggled(prev, i))} />
                </>
              ) : phraseSaved && <Text tone="muted" size="s">{PHRASE_SAVED}</Text>}
            </>
          )}
        </Stack>
        {error && <Text tone="err" size="s">{error}</Text>}
        <Button variant="fill" wide busy={adding} onClick={add}>{tab === 'phrase' ? 'Add phrase' : 'Add source'}</Button>
      </Stack>
      {questions && (
        <QuestionsModal questions={questions} onCancel={() => setQuestions(null)} onConfirm={answer} />
      )}
    </>
  )
}
