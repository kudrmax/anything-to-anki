import { Outlet } from 'react-router-dom'
import '@/styles/base.css'
import { useApplyTheme } from '@/lib/theme'
import { TopNav } from './TopNav'
import { AnkiProblemsBanner } from './AnkiProblemsBanner'
import css from './AppShell.module.css'

export function AppShell() {
  useApplyTheme()
  return (
    <div className={css.shell}>
      <TopNav />
      <AnkiProblemsBanner />
      <main className={css.main}>
        <Outlet />
      </main>
    </div>
  )
}
