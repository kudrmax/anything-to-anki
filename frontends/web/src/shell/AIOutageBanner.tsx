import type { AIOutage } from '@/api/types'
import { Banner, Text } from '@/ui'

export function AIOutageBanner({ outage }: { outage: AIOutage }) {
  return (
    <Banner tone="warn">
      AI unavailable — {outage.reason}
      {outage.queue_waits && <Text size="s" tone="soft" block>The queue waits and resumes on its own</Text>}
    </Banner>
  )
}
