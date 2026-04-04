import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout'
import { InboxPage } from '@/pages/InboxPage'
import { ReviewPage } from '@/pages/ReviewPage'
import { ExportPage } from '@/pages/ExportPage'
import { SettingsPage } from '@/pages/SettingsPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<InboxPage />} />
          <Route path="/sources/:id/review" element={<ReviewPage />} />
          <Route path="/sources/:id/export" element={<ExportPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
