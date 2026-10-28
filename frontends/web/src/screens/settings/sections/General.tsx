import type { ThemePref } from '@/lib/preferences'
import { useTheme } from '@/lib/theme'
import { DividerRow, Segmented } from '@/ui'
import { Updates } from '../UpdatesSection'
import { Group } from './Group'

const THEMES: { value: ThemePref; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
]

export function General() {
  const { pref, setPref } = useTheme()
  return (
    <>
      <Group title="Appearance">
        <DividerRow last label="Theme">
          <Segmented value={pref} options={THEMES} onChange={setPref} />
        </DividerRow>
      </Group>
      <Group title="Updates">
        <Updates />
      </Group>
    </>
  )
}
