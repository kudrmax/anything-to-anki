import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Page, PageHeader } from '@/shell'
import { Button, Empty, Spinner, Text } from '@/ui'
import { AiModel, Anki, Appearance, KnownWords, MediaStorage, ReviewPrefs, Tts, Vocabulary } from './SettingsSections'
import { useSettings } from './useSettings'
import css from './settings.module.css'

const SECTION_PARAM = 'section'

interface Section {
  id: string
  title: string
  content: ReactNode
  /** Раздел меняет сохраняемые настройки: под ним кнопка Save. */
  saved?: boolean
  count?: number
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

  const sections: Section[] = [
    { id: 'appearance', title: 'Appearance', content: <Appearance /> },
    { id: 'anki', title: 'Anki', content: <Anki store={store} form={form} />, saved: true },
    { id: 'vocabulary', title: 'Vocabulary', content: <Vocabulary store={store} form={form} />, saved: true },
    { id: 'review', title: 'Review', content: <ReviewPrefs /> },
    { id: 'ai-model', title: 'AI model', content: <AiModel store={store} form={form} />, saved: true },
    { id: 'tts', title: 'Text-to-speech', content: <Tts store={store} form={form} />, saved: true },
    { id: 'known-words', title: 'Known words', content: <KnownWords store={store} />, count: store.knownWords.length },
    { id: 'media-storage', title: 'Media storage', content: <MediaStorage store={store} /> },
  ]
  const active = sections.find(section => section.id === params.get(SECTION_PARAM)) ?? sections[0]
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
              {section.count !== undefined && <span className={css.count}>{section.count}</span>}
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
