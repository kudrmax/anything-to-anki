import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Page, PageHeader } from '@/shell'
import { Button, Empty, Spinner, Text } from '@/ui'
import { Anki } from './sections/Anki'
import { General } from './sections/General'
import { Generation } from './sections/Generation'
import { Review } from './sections/Review'
import { Sources } from './sections/Sources'
import { Vocabulary } from './sections/Vocabulary'
import { WordLists, type WordListKind } from './sections/WordLists'
import { useSettings } from './useSettings'
import css from './settings.module.css'

const SECTION_PARAM = 'section'
const LIST_PARAM = 'list'
const WORD_LISTS: WordListKind[] = ['known', 'learning', 'unknown']

/** Ссылки на разделы до их объединения ведут в раздел, где эти настройки теперь. */
const MOVED_SECTIONS: Record<string, { section: string; list?: WordListKind }> = {
  appearance: { section: 'general' },
  updates: { section: 'general' },
  'card-layout': { section: 'review' },
  'ai-model': { section: 'generation' },
  tts: { section: 'generation' },
  pictures: { section: 'generation' },
  books: { section: 'sources' },
  'media-storage': { section: 'sources' },
  'known-words': { section: 'words', list: 'known' },
  learning: { section: 'words', list: 'learning' },
  'unknown-words': { section: 'words', list: 'unknown' },
}

interface Section {
  id: string
  title: string
  content: ReactNode
  /** Раздел меняет сохраняемые настройки: под ним кнопка Save. */
  saved?: boolean
}

export function SettingsScreen() {
  const store = useSettings()
  const [params, setParams] = useSearchParams()

  const { form } = store
  if (store.loading || !form) {
    return (
      <Page wide header={<PageHeader title="Settings" />}>
        <Empty>{store.saveError ? <Text tone="err">{store.saveError}</Text> : <Spinner />}</Empty>
      </Page>
    )
  }

  const requested = params.get(SECTION_PARAM) ?? ''
  const moved = MOVED_SECTIONS[requested]
  const sectionId = moved?.section ?? requested
  const listParam = moved?.list ?? params.get(LIST_PARAM)
  const list = WORD_LISTS.find(kind => kind === listParam) ?? 'known'
  const openList = (next: WordListKind) => setParams({ [SECTION_PARAM]: 'words', [LIST_PARAM]: next }, { replace: true })

  const sections: Section[] = [
    { id: 'general', title: 'General', content: <General /> },
    { id: 'vocabulary', title: 'Vocabulary', content: <Vocabulary store={store} form={form} />, saved: true },
    { id: 'words', title: 'Word lists', content: <WordLists store={store} list={list} onList={openList} /> },
    { id: 'generation', title: 'Generation', content: <Generation store={store} form={form} />, saved: true },
    { id: 'review', title: 'Review', content: <Review store={store} form={form} />, saved: true },
    { id: 'anki', title: 'Anki', content: <Anki store={store} form={form} />, saved: true },
    { id: 'sources', title: 'Sources', content: <Sources store={store} form={form} />, saved: true },
  ]
  const active = sections.find(section => section.id === sectionId) ?? sections[0]
  const open = (id: string) => setParams({ [SECTION_PARAM]: id }, { replace: true })

  return (
    <Page wide header={<PageHeader title="Settings" />}>
      <div className={css.layout}>
        <nav className={css.nav}>
          {sections.map(section => (
            <button
              key={section.id}
              type="button"
              className={section.id === active.id ? `${css.navItem} ${css.on}` : css.navItem}
              aria-current={section.id === active.id ? 'page' : undefined}
              onClick={() => open(section.id)}
            >
              {section.title}
            </button>
          ))}
        </nav>
        <section className={css.panel}>
          <h2 className={css.heading}>{active.title}</h2>
          {active.content}
          {active.saved && (
            <div className={css.save}>
              {store.saveError && <Text tone="err">{store.saveError}</Text>}
              <Button variant="fill" busy={store.saving} onClick={() => void store.save()}>{store.saved ? 'Saved ✓' : 'Save settings'}</Button>
            </div>
          )}
        </section>
      </div>
    </Page>
  )
}
