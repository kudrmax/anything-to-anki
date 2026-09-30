import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './styles/tokens.css'
// Inter едет в собственном бандле, а не с fonts.googleapis.com: приложение
// локальное и должно рисовать первый экран без доступа в интернет.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
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
