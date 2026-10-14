import { Page, PageHeader } from '@/shell'
import { statsStore } from '@/hooks/useStats'
import { Toast, useToast } from '@/ui'
import { AddSourceForm } from './AddSourceForm'
import css from './sources.module.css'

const ADDED_MESSAGE = 'Added to Sources'

/** Экран добавления источника, темы или фразы. */
export function AddSourceScreen() {
  const [notice, showNotice] = useToast()
  const [warning, showWarning] = useToast()

  const added = async () => {
    showNotice(ADDED_MESSAGE)
    await statsStore.refresh()
  }

  return (
    <Page wide header={<PageHeader title="Add" />}>
      <section className={css.add}>
        <AddSourceForm onReload={added} onToast={showWarning} />
      </section>
      <Toast message={notice} />
      <Toast message={warning} tone="warn" />
    </Page>
  )
}
