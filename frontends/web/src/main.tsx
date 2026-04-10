import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { themePref } from './lib/preferences'
import { ThemeProvider } from './lib/ThemeProvider'

document.documentElement.dataset.theme = themePref.read()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
)
