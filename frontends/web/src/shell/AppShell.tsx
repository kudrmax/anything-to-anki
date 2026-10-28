import { Outlet } from 'react-router-dom'
import '@/styles/base.css'
import { useApplyTheme } from '@/lib/theme'
import { TopNav } from './TopNav'
import { AnkiProblemsBanner } from './AnkiProblemsBanner'
import { LongOperationOverlay } from './LongOperationOverlay'
import { useSettingsShortcut } from './useSettingsShortcut'
import { UpdatesProvider } from './updates/UpdatesProvider'
import { WhatsNew } from './updates/WhatsNew'
import css from './AppShell.module.css'

export function AppShell() {
  useApplyTheme()
  useSettingsShortcut()
  return (
    <UpdatesProvider>
      <div className={css.shell}>
        <TopNav />
        <AnkiProblemsBanner />
        <LongOperationOverlay />
        <main className={css.main}>
          <Outlet />
        </main>
      </div>
      <WhatsNew />
    </UpdatesProvider>
  )
}
