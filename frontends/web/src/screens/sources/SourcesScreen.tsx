import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Page, PageHeader } from '@/shell'
import type { SourceSummary } from '@/api/types'
import { Banner, Button, Empty, Stat, StatGrid, Toast, useToast } from '@/ui'
import { AddSourceForm } from './AddSourceForm'
import { CollectionFilter } from './CollectionFilter'
import { ReprocessModal } from './ReprocessModal'
import { SourceRow } from './SourceRow'
import { useSources } from './useSources'
import css from './sources.module.css'

type Stage = 'progress' | 'preparing' | 'ready' | 'reviewed'

const STAGES: { stage: Stage; label: string }[] = [
  { stage: 'progress', label: 'In progress' },
  { stage: 'preparing', label: 'Preparing' },
  { stage: 'ready', label: 'Ready to review' },
  { stage: 'reviewed', label: 'Reviewed' },
]

/** Группа списка, в которой показан источник. */
function stageOf(source: SourceSummary): Stage {
  if (source.awaiting_generation) return 'preparing'
  if (source.status === 'partially_reviewed') return 'progress'
  if (source.status === 'done') return 'ready'
  if (source.status === 'reviewed') return 'reviewed'
  return 'preparing'
}

export function SourcesScreen() {
  const navigate = useNavigate()
  const store = useSources()
  const [activeCollectionId, setActiveCollectionId] = useState<number | null>(null)
  const [reprocessSourceId, setReprocessSourceId] = useState<number | null>(null)
  const [toast, showToast] = useToast()

  const { sources, stats, collections } = store
  const filtered = activeCollectionId === null ? sources : sources.filter(s => s.collection_id === activeCollectionId)

  const review = (id: number) => navigate(`/sources/${id}/review`)
  const exportSource = (id: number) => navigate(`/sources/${id}/export`)

  const reprocess = (id: number) => {
    const source = sources.find(s => s.id === id)
    if (source?.status === 'error') void store.reprocess(id)
    else setReprocessSourceId(id)
  }

  const deleteCollection = async (id: number) => {
    const deleted = await store.deleteCollection(id)
    if (deleted && activeCollectionId === id) setActiveCollectionId(null)
  }

  const header = (
    <PageHeader title="Sources">
      <CollectionFilter
        collections={collections}
        activeId={activeCollectionId}
        onSelect={setActiveCollectionId}
        onCreate={name => void store.createCollection(name)}
        onRename={(id, name) => void store.renameCollection(id, name)}
        onDelete={id => void deleteCollection(id)}
      />
      {store.pendingCount > 0 && (
        <Button busy={store.processingAll} onClick={() => void store.processAll()}>Process all ({store.pendingCount})</Button>
      )}
    </PageHeader>
  )

  const aside = (
    <>
      <section className={`${css.add} ${css.desktopOnly}`}>
        <AddSourceForm onCreated={store.prepend} onReload={store.reload} onToast={showToast} />
      </section>
      <StatGrid>
        <Stat value={stats?.learn_count ?? 0} label="to learn" />
        <Stat value={stats?.known_word_count ?? 0} label="known words" />
        <Stat value={stats?.candidate_count ?? 0} label="candidates" wide />
      </StatGrid>
    </>
  )

  const banner = (store.error || store.vpnBlocked) && (
    <>
      {store.vpnBlocked && <Banner tone="warn">AI unavailable — turn on VPN</Banner>}
      {store.error && <Banner tone="err" onDismiss={store.clearError}>{store.error}</Banner>}
    </>
  )

  return (
    <Page wide header={header} aside={aside} banner={banner}>
      {filtered.length === 0 && (
        <Empty>{sources.length === 0 ? 'No sources yet. Add one to get started.' : 'No sources in this collection.'}</Empty>
      )}
      {STAGES.map(({ stage, label }) => {
        const group = filtered.filter(source => stageOf(source) === stage)
        if (group.length === 0) return null
        return (
          <section key={stage} className={css.group}>
            <h2 className={css.groupTitle}>{label}<span>{group.length}</span></h2>
            {group.map((source, index) => (
              <SourceRow
                key={source.id}
                source={source}
                collections={collections}
                primary={stage === 'progress' && index === 0}
                onProcess={id => void store.process(id)}
                onGenerate={id => void store.generate(id)}
                onCancelGeneration={id => void store.cancelGeneration(id)}
                onRetryGeneration={id => void store.retryGeneration(id)}
                onReview={review}
                onExport={exportSource}
                onDelete={id => void store.remove(id)}
                onRename={(id, title) => void store.rename(id, title)}
                onReprocess={reprocess}
                onAssignCollection={(sourceId, collectionId) => void store.assignCollection(sourceId, collectionId)}
              />
            ))}
          </section>
        )
      })}
      {reprocessSourceId !== null && (
        <ReprocessModal
          sourceId={reprocessSourceId}
          onClose={() => setReprocessSourceId(null)}
          onReprocess={() => { const id = reprocessSourceId; setReprocessSourceId(null); void store.reprocess(id) }}
          onOpenExport={exportSource}
        />
      )}
      <Toast message={toast} tone="warn" />
    </Page>
  )
}
