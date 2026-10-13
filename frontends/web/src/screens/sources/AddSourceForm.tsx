import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { DetectedFormat, Question } from '@/api/types'
import { nativeHost } from '@/lib/nativeHost'
import { withDroppedPaths } from '@/lib/text/sourceInput'
import { pickedWords, toggled } from '@/lib/text/words'
import { Button, Field, Segmented, Spinner, Stack, Text, TextArea, WordPicker } from '@/ui'
import css from './AddSourceForm.module.css'
import { PathField } from './PathField'
import { QuestionsModal } from './QuestionsModal'
import { useFileDrag } from './useFileDrag'

/** Чем станет введённое: источником, темой или сохранённой фразой. */
type Mode = 'source' | 'topic' | 'phrase'

const MODES: { value: Mode; label: string }[] = [
  { value: 'source', label: 'Source' },
  { value: 'topic', label: 'Topic' },
  { value: 'phrase', label: 'Phrase' },
]
const INPUT_PLACEHOLDER = 'Paste text, a file path, a link — or a topic, a phrase…'
const TOPIC_HINT = 'Targets come from AI, phrases from your sources'
const PHRASE_HINT = 'Tap words to select target'
const PHRASE_SAVED = 'Phrase saved'
const SUBTITLE_EXTENSIONS = ['srt']
const NO_SUBTITLES_ERROR = 'subtitles_not_available'
const DROP_HINT = 'Drop the file here'
const BROWSER_DROP_ERROR = 'Dropped files reach the app only in the macOS app — enter the path instead'
const DETECT_DELAY_MS = 300
const ADD_LABEL: Record<Mode, string> = { source: 'Add source', topic: 'Add topic', phrase: 'Add phrase' }

interface AddSourceFormProps {
  onReload: () => Promise<void>
  onToast: (message: string) => void
}

const messageOf = (e: unknown): string => (e instanceof Error ? e.message : String(e))

export function AddSourceForm({ onReload, onToast }: AddSourceFormProps) {
  const [mode, setMode] = useState<Mode>('source')
  const [input, setInput] = useState('')
  const [title, setTitle] = useState('')
  const [srtPath, setSrtPath] = useState('')
  const [detected, setDetected] = useState<DetectedFormat | null>(null)
  const [detecting, setDetecting] = useState(false)
  const [phraseTarget, setPhraseTarget] = useState<Set<number>>(new Set())
  const [phraseSaved, setPhraseSaved] = useState(false)
  const [adding, setAdding] = useState(false)
  const [picking, setPicking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [questions, setQuestions] = useState<Question[] | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [host] = useState(() => nativeHost())

  const entered = input.trim() !== ''

  const edit = (value: string) => {
    setInput(value)
    setPhraseTarget(new Set())
    setPhraseSaved(false)
    setError(null)
  }

  const reset = () => {
    setInput('')
    setTitle('')
    setSrtPath('')
    setAnswers({})
    setPhraseTarget(new Set())
    setMode('source')
  }

  const fileDrag = useFileDrag({
    onEnter: () => setError(null),
    onBrowserDrop: () => setError(BROWSER_DROP_ERROR),
  })
  const resetFileDrag = fileDrag.reset

  useEffect(() => host?.onFileDrop(paths => {
    resetFileDrag()
    setError(null)
    setMode('source')
    const chosen = withDroppedPaths({ filePath: input, srtPath }, paths)
    edit(chosen.filePath)
    setSrtPath(chosen.srtPath)
  }), [host, input, srtPath, resetFileDrag])

  // Подсказку под полем считает backend: как он прочитает то, что вставлено.
  useEffect(() => {
    if (mode !== 'source' || !entered) { setDetected(null); setDetecting(false); return }
    const controller = new AbortController()
    setDetecting(true)
    const timer = window.setTimeout(() => {
      api.detectFormat(input, controller.signal)
        .then(found => { setDetected(found); setDetecting(false) })
        .catch(() => {})
    }, DETECT_DELAY_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [input, mode, entered])

  const isVideo = detected?.format === 'video_file'

  const pickFile = async () => {
    if (!host) return
    setPicking(true)
    try {
      const path = await host.pickFile()
      if (path) {
        setMode('source')
        edit(path)
        setSrtPath('')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open the file picker')
    } finally {
      setPicking(false)
    }
  }

  const run = async (action: () => Promise<void>) => {
    setAdding(true)
    try {
      await action()
    } catch (e) {
      const message = messageOf(e)
      if (message.includes(NO_SUBTITLES_ERROR)) onToast('Subtitles are not available for this video')
      else setError(message)
    } finally {
      setAdding(false)
    }
  }

  const submitSource = (given: Record<string, string>) => run(async () => {
    const result = await api.addSource(input, isVideo ? srtPath.trim() : '', title.trim(), given)
    if ('questions' in result) {
      setAnswers(given)
      setQuestions(result.questions)
      return
    }
    reset()
    await onReload()
  })

  const answer = (given: Record<string, string>) => {
    setQuestions(null)
    void submitSource({ ...answers, ...given })
  }

  const addTopic = () => run(async () => {
    await api.createTopic(input.trim(), title.trim() || undefined)
    reset()
    await onReload()
  })

  const addPhrase = () => {
    const target = pickedWords(input, phraseTarget)
    if (!target) { setError('Select target words'); return }
    void run(async () => {
      await api.addSavedPhrase(input.trim(), target)
      reset()
      setPhraseSaved(true)
      await onReload()
    })
  }

  const add = () => {
    setError(null)
    if (mode === 'topic') void addTopic()
    else if (mode === 'phrase') addPhrase()
    else void submitSource({})
  }

  return (
    <>
      <Stack gap="m">
        <Stack>
          {fileDrag.dragging && <div className={css.dropZone}>{DROP_HINT}</div>}
          <TextArea value={input} placeholder={INPUT_PLACEHOLDER} onChange={e => edit(e.target.value)} />
          {!entered && host && !fileDrag.dragging && (
            <div className={css.hintRow}>
              <Text tone="muted" size="s">or drag a file here</Text>
              <Button variant="link" busy={picking} onClick={pickFile}>Choose…</Button>
            </div>
          )}
          {!entered && phraseSaved && <Text tone="muted" size="s">{PHRASE_SAVED}</Text>}
        </Stack>
        {entered && (
          <>
            <div className={css.modeRow}>
              <Segmented value={mode} options={MODES} onChange={setMode} />
              {mode === 'source' && (detecting ? <Spinner /> : detected && <Text tone="muted" size="s">{detected.label}</Text>)}
            </div>
            {mode === 'source' && (
              <Stack>
                {isVideo && !detecting && (
                  <PathField value={srtPath} placeholder="/path/to/subtitles.srt (optional)" extensions={SUBTITLE_EXTENSIONS} onChange={setSrtPath} onError={setError} />
                )}
                <Field value={title} placeholder="Title (optional)" onChange={e => setTitle(e.target.value)} />
              </Stack>
            )}
            {mode === 'topic' && (
              <Stack>
                <Text tone="muted" size="s">{TOPIC_HINT}</Text>
                <Field value={title} placeholder="Title (optional)" onChange={e => setTitle(e.target.value)} />
              </Stack>
            )}
            {mode === 'phrase' && (
              <Stack>
                <Text tone="muted" size="s">{PHRASE_HINT}</Text>
                <WordPicker phrase={input} selected={phraseTarget} onToggle={i => setPhraseTarget(prev => toggled(prev, i))} />
              </Stack>
            )}
            {error && <Text tone="err" size="s">{error}</Text>}
            <Button variant="fill" wide busy={adding} onClick={add}>{ADD_LABEL[mode]}</Button>
          </>
        )}
        {!entered && error && <Text tone="err" size="s">{error}</Text>}
      </Stack>
      {questions && (
        <QuestionsModal questions={questions} onCancel={() => setQuestions(null)} onConfirm={answer} />
      )}
    </>
  )
}
