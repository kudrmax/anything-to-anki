import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Page, PageHeader } from '@/shell'
import { Empty, Spinner, Text } from '@/ui'
import { Anki } from './sections/Anki'
import { Cards } from './sections/Cards'
import { General } from './sections/General'
import { MyWords, type WordListKind } from './sections/MyWords'
import { Sources } from './sections/Sources'
import { Words } from './sections/Words'
import { SaveStatus } from './SaveStatus'
import { useSettings } from './useSettings'
import css from './settings.module.css'

const SECTION_PARAM = 'section'
const LIST_PARAM = 'list'
const WORD_LISTS: WordListKind[] = ['known', 'learning', 'unknown']

/** Ссылки на разделы до их объединения ведут в раздел, где эти настройки теперь. */
const MOVED_SECTIONS: Record<string, { section: string; list?: WordListKind }> = {
  appearance: { section: 'general' },
  updates: { section: 'general' },
  vocabulary: { section: 'words' },
  'known-words': { section: 'my-words', list: 'known' },
  learning: { section: 'my-words', list: 'learning' },
  'unknown-words': { section: 'my-words', list: 'unknown' },
  review: { section: 'cards' },
  'card-layout': { section: 'cards' },
  'ai-model': { section: 'cards' },
  tts: { section: 'cards' },
  pictures: { section: 'cards' },
  books: { section: 'sources' },
  'media-storage': { section: 'sources' },
}

interface Section {
  id: string
  title: string
  content: ReactNode
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
  const openList = (next: WordListKind) => setParams({ [SECTION_PARAM]: 'my-words', [LIST_PARAM]: next }, { replace: true })

  const sections: Section[] = [
    { id: 'general', title: 'General', content: <General /> },
    { id: 'words', title: 'Words', content: <Words store={store} form={form} /> },
    { id: 'my-words', title: 'My words', content: <MyWords store={store} list={list} onList={openList} /> },
    { id: 'cards', title: 'Cards', content: <Cards store={store} form={form} /> },
    { id: 'anki', title: 'Anki', content: <Anki store={store} form={form} /> },
    { id: 'sources', title: 'Sources', content: <Sources store={store} form={form} /> },
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
          <div className={css.headingRow}>
            <h2 className={css.heading}>{active.title}</h2>
            <SaveStatus saving={store.saving} savedAt={store.savedAt} error={store.saveError} />
          </div>
          {active.content}
        </section>
      </div>
    </Page>
  )
}
