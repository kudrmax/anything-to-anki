import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { AIUsageStats, UsagePeriod } from '@/api/types'
import { Page, PageHeader } from '@/shell'
import { Empty, Segmented, Spinner, Stat, StatGrid } from '@/ui'
import { FeatureTable } from './FeatureTable'
import { UsageChart } from './UsageChart'
import { formatChange, formatCount, formatDay, formatTokens, PERIOD_OPTIONS } from './usageFormat'
import css from './usage.module.css'

const DEFAULT_PERIOD: UsagePeriod = '30d'
const TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone

export function UsageScreen() {
  const [period, setPeriod] = useState<UsagePeriod>(DEFAULT_PERIOD)
  const [stats, setStats] = useState<AIUsageStats | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    api.getUsage(period, TIMEZONE)
      .then(result => {
        if (cancelled) return
        setStats(result)
        setFailed(false)
      })
      .catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [period])

  const header = (
    <PageHeader title="Usage">
      <Segmented value={period} options={PERIOD_OPTIONS} onChange={setPeriod} />
    </PageHeader>
  )

  if (failed) {
    return <Page wide header={header}><Empty>Couldn't load token usage.</Empty></Page>
  }
  if (!stats) {
    return <Page wide header={header}><Empty><Spinner /></Empty></Page>
  }
  if (stats.tracking_since === null) {
    return (
      <Page wide header={header}>
        <Empty>No AI calls recorded yet. Token usage is tracked from now on.</Empty>
      </Page>
    )
  }

  const { totals } = stats
  const aside = (
    <StatGrid>
      <Stat
        value={formatTokens(totals.tokens.total)}
        label="Tokens"
        hint={totals.change_percent !== null && formatChange(totals.change_percent, stats.period)}
      />
      <Stat
        value={formatCount(totals.requests)}
        label="AI runs"
        hint={totals.failed_requests > 0 && `${formatCount(totals.failed_requests)} failed`}
      />
      <Stat
        value={totals.tokens_per_meaning === null ? '—' : formatTokens(totals.tokens_per_meaning)}
        label="Tokens per meaning"
      />
      <Stat small value={formatDay(stats.tracking_since)} label="Recorded since" />
    </StatGrid>
  )

  return (
    <Page wide header={header} aside={aside}>
      <section className={css.section}>
        <h2 className={css.sectionTitle}>Tokens per {stats.bucket_size}</h2>
        <UsageChart buckets={stats.buckets} bucketSize={stats.bucket_size} />
      </section>
      <section className={css.section}>
        <h2 className={css.sectionTitle}>What AI did</h2>
        {stats.features.length > 0
          ? <FeatureTable features={stats.features} />
          : <Empty>No AI calls in this period.</Empty>}
      </section>
    </Page>
  )
}
