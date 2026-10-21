import { Banner, Text } from '@/ui'

export function AIOutageBanner({ reason }: { reason: string }) {
  return (
    <Banner tone="warn">
      AI unavailable — {reason}
      <Text size="s" tone="soft" block>The queue waits and resumes on its own</Text>
    </Banner>
  )
}
