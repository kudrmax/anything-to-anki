import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell, ErrorBoundary } from '@/shell'
import { SourcesScreen } from '@/screens/sources/SourcesScreen'
import { AddSourceScreen } from '@/screens/sources/AddSourceScreen'
import { ReviewScreen } from '@/screens/review/ReviewScreen'
import { ExportScreen } from '@/screens/export/ExportScreen'
import { QueueScreen } from '@/screens/queue/QueueScreen'
import { UsageScreen } from '@/screens/usage/UsageScreen'
import { SettingsScreen } from '@/screens/settings/SettingsScreen'
import { CalibrateScreen } from '@/screens/calibrate/CalibrateScreen'
import { QUICK_ADD_PATH, QuickAddScreen } from '@/screens/quickAdd/QuickAddScreen'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={QUICK_ADD_PATH} element={<ErrorBoundary><QuickAddScreen /></ErrorBoundary>} />
        <Route element={<AppShell />}>
          <Route path="/add" element={<ErrorBoundary><AddSourceScreen /></ErrorBoundary>} />
          <Route path="/settings" element={<ErrorBoundary><SettingsScreen /></ErrorBoundary>} />
          <Route path="/calibrate" element={<ErrorBoundary><CalibrateScreen /></ErrorBoundary>} />
          <Route path="/queue" element={<ErrorBoundary><QueueScreen /></ErrorBoundary>} />
          <Route path="/usage" element={<ErrorBoundary><UsageScreen /></ErrorBoundary>} />
          <Route path="/sources/:id/export" element={<ErrorBoundary><ExportScreen /></ErrorBoundary>} />
          <Route path="/export" element={<ErrorBoundary><ExportScreen /></ErrorBoundary>} />
          <Route path="/sources/:id/review" element={<ErrorBoundary><ReviewScreen /></ErrorBoundary>} />
          <Route path="/" element={<ErrorBoundary><SourcesScreen /></ErrorBoundary>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
