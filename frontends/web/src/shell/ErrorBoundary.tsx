import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { Banner, Button, Stack } from '@/ui'
import css from './ErrorBoundary.module.css'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
  componentStack: string | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: null }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.setState({ componentStack: info.componentStack ?? null })
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render(): ReactNode {
    const { error, componentStack } = this.state
    if (!error) return this.props.children

    return (
      <div className={css.boundary}>
        <Stack gap="m">
          <Banner tone="err">Something went wrong</Banner>
          <pre className={css.trace}>{error.message}</pre>
          {componentStack && <pre className={css.trace}>{componentStack.trim()}</pre>}
          <div><Button onClick={() => window.location.reload()}>Reload page</Button></div>
        </Stack>
      </div>
    )
  }
}
