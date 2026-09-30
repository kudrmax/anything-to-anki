import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout'
import { AppShell } from '@/shell'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { SourcesScreen } from '@/screens/sources/SourcesScreen'
import { ReviewScreen } from '@/screens/review/ReviewScreen'
import { ExportScreen } from '@/screens/export/ExportScreen'
import { QueuePage } from '@/pages/QueuePage'
import { SettingsPage } from '@/pages/SettingsPage'
import { CalibratePage } from '@/pages/CalibratePage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/sources/:id/export" element={<ErrorBoundary><ExportScreen /></ErrorBoundary>} />
          <Route path="/export" element={<ErrorBoundary><ExportScreen /></ErrorBoundary>} />
          <Route path="/sources/:id/review" element={<ErrorBoundary><ReviewScreen /></ErrorBoundary>} />
          <Route path="/" element={<ErrorBoundary><SourcesScreen /></ErrorBoundary>} />
        </Route>
        <Route element={<AppLayout />}>
          <Route path="/queue" element={<ErrorBoundary><QueuePage /></ErrorBoundary>} />
          <Route path="/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
          <Route path="/calibrate" element={<ErrorBoundary><CalibratePage /></ErrorBoundary>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
