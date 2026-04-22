import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { InboxPage } from '@/pages/InboxPage'
import { ReviewPage } from '@/pages/ReviewPage'
import { ExportPage } from '@/pages/ExportPage'
import { GlobalExportPage } from '@/pages/GlobalExportPage'
import { QueuePage } from '@/pages/QueuePage'
import { SettingsPage } from '@/pages/SettingsPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<ErrorBoundary><InboxPage /></ErrorBoundary>} />
          <Route path="/sources/:id/review" element={<ErrorBoundary><ReviewPage /></ErrorBoundary>} />
          <Route path="/sources/:id/export" element={<ErrorBoundary><ExportPage /></ErrorBoundary>} />
          <Route path="/export" element={<ErrorBoundary><GlobalExportPage /></ErrorBoundary>} />
          <Route path="/queue" element={<ErrorBoundary><QueuePage /></ErrorBoundary>} />
          <Route path="/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
