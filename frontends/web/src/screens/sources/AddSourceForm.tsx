import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import type { InputDescription, InputKind, Question } from '@/api/types'
import { droppedPathsIn, nativeHost } from '@/lib/nativeHost'
import { withDroppedPaths } from '@/lib/text/sourceInput'
import { phraseWords, pickedIndices, toggled } from '@/lib/text/words'
import { Button, Field, Segmented, Spinner, Stack, Text, TextArea, WordPicker } from '@/ui'
import css from './AddSourceForm.module.css'
import { PathField } from './PathField'
import { QuestionsModal } from './QuestionsModal'
import { useFileDrag } from './useFileDrag'

/** Чем станет введённое: источником, темой или сохранённой фразой. */
type Mode = InputKind

const MODES: { value: Mode; label: string }[] = [
  { value: 'source', label: 'Source' },
  { value: 'topic', label: 'Topic' },
  { value: 'phrase', label: 'Phrase' },
]
const INPUT_PLACEHOLDER = 'Paste text, a file path, a link — or a topic, a phrase…'
const TOPIC_HINT = 'AI picks targets, phrases come from your sources'
const PHRASE_HINT = 'Tap the words you want to learn'
const PHRASE_SAVED = 'Phrase saved'
const SUBTITLE_EXTENSIONS = ['srt']
const NO_SUBTITLES_ERROR = 'subtitles_not_available'
const DROP_HINT = 'Drop the file here'
const BROWSER_DROP_ERROR = 'Dropped files reach the app only in the macOS app — enter the path instead'
const DESCRIBE_DELAY_MS = 300
const ADD_LABEL: Record<Mode, string> = { source: 'Add source', topic: 'Add topic', phrase: 'Add phrase' }

interface AddSourceFormProps {
  onReload: () => Promise<void>
  onToast: (message: string) => void
}

const messageOf = (e: unknown): string => (e instanceof Error ? e.message : String(e))

export function AddSourceForm({ onReload, onToast }: AddSourceFormProps) {
  const { state: navigationState, pathname, search } = useLocation()
  const navigate = useNavigate()
  // Файл бросили на экран Sources: он открыл Add и передал пути сюда.
  const [dropped] = useState(() => withDroppedPaths({ filePath: '', srtPath: '' }, droppedPathsIn(navigationState)))
  // Пути забраны в поле: в истории им не место, иначе «назад-вперёд» или перезагрузка вставят их снова.
  const carriesPaths = droppedPathsIn(navigationState).length > 0
  useEffect(() => {
    if (carriesPaths) navigate(pathname + search, { replace: true, state: null })
  }, [carriesPaths, navigate, pathname, search])
  // Режим, который пользователь переключил руками; пока его нет — режим, предложенный backend.
  const [chosen, setChosen] = useState<Mode | null>(null)
  const [input, setInput] = useState(dropped.filePath)
  const [title, setTitle] = useState('')
  const [srtPath, setSrtPath] = useState(dropped.srtPath)
  const [described, setDescribed] = useState<InputDescription | null>(null)
  const [describing, setDescribing] = useState(false)
  const [phraseTarget, setPhraseTarget] = useState<Set<number>>(new Set())
  const [phraseSaved, setPhraseSaved] = useState(false)
  const [adding, setAdding] = useState(false)
  const [picking, setPicking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [questions, setQuestions] = useState<Question[] | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [host] = useState(() => nativeHost())

  const entered = input.trim() !== ''
  const problem = described?.problem ? described : null
  const mode: Mode | null = chosen ?? described?.kind ?? null

  const edit = useCallback((value: string) => {
    setInput(value)
    // Набор с клавиатуры не трогает ручной выбор; пустое поле — начало нового ввода.
    if (!value.trim()) setChosen(null)
    setPhraseTarget(new Set())
    setPhraseSaved(false)
    setError(null)
  }, [])

  /** Ввод заменён целиком — вставкой, перетаскиванием или выбором файла: прежний выбор к нему не относится. */
  const replace = useCallback((value: string) => {
    setChosen(null)
    edit(value)
  }, [edit])

  const reset = () => {
    setInput('')
    setTitle('')
    setSrtPath('')
    setAnswers({})
    setPhraseTarget(new Set())
    setChosen(null)
  }

  const fileDrag = useFileDrag({
    onEnter: () => setError(null),
    onBrowserDrop: () => setError(BROWSER_DROP_ERROR),
  })
  const resetFileDrag = fileDrag.reset

  useEffect(() => host?.onFileDrop(paths => {
    resetFileDrag()
    setError(null)
    const chosenPaths = withDroppedPaths({ filePath: input, srtPath }, paths)
    replace(chosenPaths.filePath)
    setSrtPath(chosenPaths.srtPath)
  }), [host, input, srtPath, resetFileDrag, replace])

  // Что станет из ввода, решает backend; пока ответ в пути, на экране остаётся прежний.
  useEffect(() => {
    if (!entered) { setDescribed(null); setDescribing(false); return }
    const controller = new AbortController()
    setDescribing(true)
    const timer = window.setTimeout(() => {
      api.describeInput(input, controller.signal)
        .then(found => { setDescribed(found); setDescribing(false) })
        .catch(() => {})
    }, DESCRIBE_DELAY_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [input, entered])

  const isVideo = described?.format === 'video_file'

  const pickFile = async () => {
    if (!host) return
    setPicking(true)
    try {
      const path = await host.pickFile()
      if (path) {
        replace(path)
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
    if (!phraseTarget.size) { setError('Select target words'); return }
    void run(async () => {
      await api.addSavedPhrase(input, pickedIndices(phraseTarget))
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

  const modeDetail = mode === 'source' ? described?.label : mode === 'topic' ? TOPIC_HINT : PHRASE_HINT

  return (
    <>
      <Stack gap="m">
        <Stack>
          {fileDrag.dragging && <div className={css.dropZone}>{DROP_HINT}</div>}
          <TextArea
            className={problem ? css.problemField : undefined}
            value={input}
            placeholder={INPUT_PLACEHOLDER}
            onPaste={() => setChosen(null)}
            onChange={e => edit(e.target.value)}
          />
          {!entered && host && !fileDrag.dragging && (
            <div className={css.hintRow}>
              <Text tone="muted" size="s">or drag a file here</Text>
              <Button variant="link" busy={picking} onClick={pickFile}>Choose…</Button>
            </div>
          )}
          {!entered && phraseSaved && <Text tone="muted" size="s">{PHRASE_SAVED}</Text>}
        </Stack>
        {entered && problem && (
          <>
            <div className={css.problem}>
              <Text tone="err" size="s">{problem.problem_message}</Text>
              {problem.problem_hint && <Text tone="muted" size="s">{problem.problem_hint}</Text>}
            </div>
            <Button variant="fill" wide disabled>{ADD_LABEL.source}</Button>
          </>
        )}
        {entered && !problem && mode && (
          <>
            <div className={css.modeRow}>
              <Segmented value={mode} options={MODES} onChange={setChosen} />
              {describing ? <Spinner /> : modeDetail && <Text tone="muted">{modeDetail}</Text>}
            </div>
            {mode !== 'phrase' && (
              <Field value={title} placeholder="Title (optional)" onChange={e => setTitle(e.target.value)} />
            )}
            {mode === 'source' && isVideo && (
              <PathField value={srtPath} placeholder="/path/to/subtitles.srt (optional)" extensions={SUBTITLE_EXTENSIONS} onChange={setSrtPath} onError={setError} />
            )}
            {mode === 'phrase' && (
              <WordPicker words={phraseWords(input)} selected={phraseTarget} onToggle={i => setPhraseTarget(prev => toggled(prev, i))} />
            )}
            {error && <Text tone="err" size="s">{error}</Text>}
            <Button variant="fill" wide busy={adding} onClick={add}>{ADD_LABEL[mode]}</Button>
          </>
        )}
        {entered && !described && describing && <Spinner />}
        {!entered && error && <Text tone="err" size="s">{error}</Text>}
      </Stack>
      {questions && (
        <QuestionsModal questions={questions} onCancel={() => setQuestions(null)} onConfirm={answer} />
      )}
    </>
  )
}
