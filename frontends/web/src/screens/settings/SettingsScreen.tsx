import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Aside, Page, PageHeader } from '@/shell'
import { Button, Empty, Spinner, Text } from '@/ui'
import { AiModel, Anki, Appearance, KnownWords, MediaStorage, ReviewPrefs, Tts, UsagePriority, Vocabulary } from './SettingsSections'
import { useSettings } from './useSettings'
import css from './settings.module.css'

const SPY_MARGIN = '-10% 0% -70% 0%'

export function SettingsScreen() {
  const store = useSettings()
  const contentRef = useRef<HTMLDivElement>(null)
  const [activeId, setActiveId] = useState('appearance')
  const ready = !store.loading && store.form !== null

  // Подсветка текущей секции в оглавлении по прокрутке.
  useEffect(() => {
    if (!ready || !contentRef.current) return
    const observer = new IntersectionObserver(entries => {
      const visible = entries.find(entry => entry.isIntersecting)
      if (visible) setActiveId(visible.target.id)
    }, { rootMargin: SPY_MARGIN })
    contentRef.current.querySelectorAll('section').forEach(section => observer.observe(section))
    return () => observer.disconnect()
  }, [ready])

  const { form } = store
  if (store.loading || !form) {
    return (
      <Page header={<PageHeader title="Settings" />}>
        <Empty>{store.saveError ? <Text tone="err">{store.saveError}</Text> : <Spinner />}</Empty>
      </Page>
    )
  }

  const sections: { id: string; title: string; content: ReactNode }[] = [
    { id: 'appearance', title: 'Appearance', content: <Appearance /> },
    { id: 'anki', title: 'Anki', content: <Anki store={store} form={form} /> },
    { id: 'vocabulary', title: 'Vocabulary', content: <Vocabulary store={store} form={form} /> },
    { id: 'usage-priority', title: 'Usage priority', content: <UsagePriority store={store} form={form} /> },
    { id: 'review', title: 'Review', content: <ReviewPrefs /> },
    { id: 'ai-model', title: 'AI model', content: <AiModel store={store} form={form} /> },
    { id: 'tts', title: 'Text-to-speech', content: <Tts store={store} form={form} /> },
    { id: 'known-words', title: `Known words (${store.knownWords.length})`, content: <KnownWords store={store} /> },
    { id: 'media-storage', title: 'Media storage', content: <MediaStorage store={store} /> },
  ]

  const jump = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setActiveId(id)
  }

  const aside = (
    <Aside title="Sections">
      <nav className={css.toc}>
        {sections.map(section => (
          <Button key={section.id} variant={section.id === activeId ? 'accent-link' : 'link'} onClick={() => jump(section.id)}>
            {section.title}
          </Button>
        ))}
      </nav>
    </Aside>
  )

  return (
    <Page header={<PageHeader title="Settings" />} aside={aside}>
      <div ref={contentRef} className={css.content}>
        {sections.map(section => (
          <section key={section.id} id={section.id} className={css.section}>
            <h2 className={css.heading}>{section.title}</h2>
            {section.content}
          </section>
        ))}
        <div className={css.save}>
          {store.saveError && <Text tone="err">{store.saveError}</Text>}
          <Button variant="fill" busy={store.saving} onClick={() => void store.save()}>{store.saved ? 'Saved ✓' : 'Save settings'}</Button>
        </div>
      </div>
    </Page>
  )
}
