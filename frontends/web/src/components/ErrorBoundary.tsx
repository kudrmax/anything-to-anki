import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

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
      <div
        className="flex-1 flex flex-col items-center justify-center p-8 gap-4"
        style={{ background: 'var(--base)' }}
      >
        <div
          className="w-full max-w-2xl rounded-xl p-6 flex flex-col gap-4"
          style={{ border: '1px solid rgba(239,68,68,.4)', background: 'rgba(239,68,68,.06)' }}
        >
          <h2 className="text-base font-semibold" style={{ color: '#f87171' }}>
            Something went wrong
          </h2>
          <pre
            className="text-xs overflow-auto rounded-lg p-3 leading-relaxed"
            style={{ color: '#fca5a5', background: 'rgba(0,0,0,.3)', maxHeight: '240px' }}
          >
            {error.message}
          </pre>
          {componentStack && (
            <pre
              className="text-xs overflow-auto rounded-lg p-3 leading-relaxed"
              style={{ color: 'var(--td)', background: 'rgba(0,0,0,.3)', maxHeight: '240px' }}
            >
              {componentStack.trim()}
            </pre>
          )}
          <button
            onClick={() => window.location.reload()}
            className="self-start rounded-lg px-4 py-1.5 text-sm font-medium cursor-pointer"
            style={{ background: 'rgba(239,68,68,.2)', color: '#f87171', border: '1px solid rgba(239,68,68,.4)' }}
          >
            Reload page
          </button>
        </div>
      </div>
    )
  }
}
