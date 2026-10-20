import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { CollectionTree, InputDescription, InputKind, Naming, NamingRequired, Question } from '@/api/types'
import { Plus } from 'lucide-react'
import { nativeHost } from '@/lib/nativeHost'
import { PATH_SEPARATOR, withDroppedPaths } from '@/lib/text/sourceInput'
import { phraseWords, pickedIndices, toggled } from '@/lib/text/words'
import { Button, Field, Icon, Segmented, Spinner, Text, TextArea, WordPicker } from '@/ui'
import css from './AddSourceForm.module.css'
import { PathField } from './PathField'
import { NamingModal } from './NamingModal'
import { QuestionsModal } from './QuestionsModal'
import { useFileDrag } from './useFileDrag'

/** Чем станет введённое: источником, темой или сохранённой фразой. */
type Mode = InputKind

const MODES: { value: Mode; label: string }[] = [
  { value: 'source', label: 'Source' },
  { value: 'topic', label: 'Topic' },
  { value: 'phrase', label: 'Phrase' },
]
const INPUT_PLACEHOLDER = 'Paste a link or text, type a topic or a phrase — or drop a file'
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
  // Режим, который пользователь переключил руками; пока его нет — режим, предложенный backend.
  const [chosen, setChosen] = useState<Mode | null>(null)
  const [input, setInput] = useState('')
  const [title, setTitle] = useState('')
  const [srtPath, setSrtPath] = useState('')
  const [described, setDescribed] = useState<InputDescription | null>(null)
  const [describing, setDescribing] = useState(false)
  const [phraseTarget, setPhraseTarget] = useState<Set<number>>(new Set())
  const [phraseSaved, setPhraseSaved] = useState(false)
  const [adding, setAdding] = useState(false)
  const [picking, setPicking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [questions, setQuestions] = useState<Question[] | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>[]>([])
  const [naming, setNaming] = useState<NamingRequired | null>(null)
  const [tree, setTree] = useState<CollectionTree | null>(null)
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
    setAnswers([])
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
  const several = described?.several === true

  const pickFile = async () => {
    if (!host) return
    setPicking(true)
    try {
      const paths = await host.pickFiles()
      if (paths.length) {
        replace(paths.join(PATH_SEPARATOR))
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

  const submitSource = (given: Record<string, string>[], named?: Naming) => run(async () => {
    const result = await api.addSource(input, isVideo ? srtPath.trim() : '', several ? '' : title.trim(), given, named)
    if ('questions' in result) {
      setAnswers(given)
      setQuestions(result.questions)
      return
    }
    if ('heading' in result) {
      setAnswers(given)
      setTree(await api.getCollectionTree())
      setNaming(result)
      return
    }
    reset()
    await onReload()
  })

  const answer = (given: Record<string, string>[]) => {
    setQuestions(null)
    const merged = Array.from({ length: Math.max(answers.length, given.length) }, (_, i) => ({ ...answers[i], ...given[i] }))
    void submitSource(merged)
  }

  const name = (named: Naming) => {
    setNaming(null)
    void submitSource(answers, named)
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
    else void submitSource([])
  }

  const modeDetail = mode === 'source' ? described?.label : mode === 'topic' ? TOPIC_HINT : PHRASE_HINT

  return (
    <>
      <section className={css.card} aria-label="Add">
        <div className={css.head}>
          <span className={css.plus}><Icon as={Plus} size="s" /></span>
          <span className={css.headTitle}>Add</span>
          {host && <Button variant="link" className={css.choose} busy={picking} onClick={pickFile}>Choose file…</Button>}
        </div>
        {fileDrag.dragging ? <div className={css.dropZone}>{DROP_HINT}</div> : (
          <TextArea
            className={problem ? `${css.area} ${css.problemField}` : css.area}
            value={input}
            placeholder={INPUT_PLACEHOLDER}
            onPaste={() => setChosen(null)}
            onChange={e => edit(e.target.value)}
          />
        )}
        {!entered && phraseSaved && <Text tone="muted" size="s">{PHRASE_SAVED}</Text>}
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
            {mode !== 'phrase' && !several && (
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
      </section>
      {questions && (
        <QuestionsModal questions={questions} onCancel={() => setQuestions(null)} onConfirm={answer} />
      )}
      {naming && (
        <NamingModal required={naming} tree={tree} onCancel={() => setNaming(null)} onConfirm={name} />
      )}
    </>
  )
}
