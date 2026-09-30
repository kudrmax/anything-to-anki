import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Aside, Page, PageHeader } from '@/shell'
import { Banner, Button, DividerRow, Empty, Progress, Toast, useToast } from '@/ui'
import { AddSourceForm } from './AddSourceForm'
import { CollectionFilter } from './CollectionFilter'
import { ReprocessModal } from './ReprocessModal'
import { SourceRow } from './SourceRow'
import { useSources } from './useSources'

export function SourcesScreen() {
  const navigate = useNavigate()
  const store = useSources()
  const [activeCollectionId, setActiveCollectionId] = useState<number | null>(null)
  const [reprocessSourceId, setReprocessSourceId] = useState<number | null>(null)
  const [toast, showToast] = useToast()

  const { sources, stats, collections, cefrLevel } = store
  const filtered = activeCollectionId === null ? sources : sources.filter(s => s.collection_id === activeCollectionId)
  const learnTotal = sources.reduce((sum, s) => sum + s.learn_count, 0)
  const candidateTotal = sources.reduce((sum, s) => sum + s.candidate_count, 0)
  const progress = candidateTotal > 0 ? learnTotal / candidateTotal : 0

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
      <Aside title="Add source">
        <AddSourceForm onCreated={store.prepend} onReload={store.reload} onToast={showToast} />
      </Aside>
      <Aside title="Progress">
        <DividerRow compact label="To learn"><b>{learnTotal}</b></DividerRow>
        <DividerRow compact label="Candidates"><b>{candidateTotal}</b></DividerRow>
        <DividerRow compact label="Sources"><b>{sources.length}</b></DividerRow>
        <DividerRow compact label="Known words"><b>{stats?.known_word_count ?? 0}</b></DividerRow>
        <DividerRow compact last label={`${cefrLevel} vocabulary`}><b>{Math.round(progress * 100)}%</b></DividerRow>
        <Progress value={progress} />
      </Aside>
    </>
  )

  return (
    <Page header={header} aside={aside} banner={store.error && <Banner tone="err" onDismiss={store.clearError}>{store.error}</Banner>}>
      {filtered.length === 0 && (
        <Empty>{sources.length === 0 ? 'No sources yet. Add one to get started.' : 'No sources in this collection.'}</Empty>
      )}
      {filtered.map(source => (
        <SourceRow
          key={source.id}
          source={source}
          collections={collections}
          onProcess={id => void store.process(id)}
          onReview={review}
          onExport={exportSource}
          onDelete={id => void store.remove(id)}
          onRename={(id, title) => void store.rename(id, title)}
          onReprocess={reprocess}
          onAssignCollection={(sourceId, collectionId) => void store.assignCollection(sourceId, collectionId)}
        />
      ))}
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
